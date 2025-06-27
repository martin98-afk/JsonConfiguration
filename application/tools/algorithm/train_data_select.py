"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: train_data_select.py
@time: 2025/6/23 15:54
@desc: 
"""
import numpy as np

from typing import Tuple, Dict, List

from loguru import logger
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

from application.base import BaseTool


class TrainDataSelect(BaseTool):
    """
    自动寻找信息量高的训练区间（支持多测点，滑窗判断）
    包含双向熵计算、K-means聚类、动态阈值调整等核心功能
    """

    def __init__(self):
        """初始化参数配置"""
        super().__init__()
        self.min_entropy = 0.001  # 熵值下限，防止除零错误
        self.cluster_num = 2  # K-means聚类数（高/低信息量）
        self.win_weight = 0.5  # 动态窗口权重衰减系数
        self.max_iter = 100  # K-means最大迭代次数

    def _entropy(self, col, bins=10):
        """计算单列数据的香农熵"""
        hist, _ = np.histogram(col, bins=bins, density=True)
        hist = hist[hist > 0]
        if len(hist) <= 1:
            return 0.0  # 单一值返回0熵
        p = hist / hist.sum()  # 归一化成概率
        return -np.sum(p * np.log2(p))  # ≥ 0

    def _dynamic_window(self, ys_mat: np.ndarray, win: int) -> np.ndarray:
        """动态窗口熵计算：覆盖早期数据"""
        scaler = MinMaxScaler()
        ys_norm = scaler.fit_transform(ys_mat)
        ent = np.zeros(len(ys_mat))

        # 权重衰减曲线（指数衰减）
        weights = np.exp(-self.win_weight * np.linspace(0, 1, win))

        for i in range(1, len(ys_mat)):
            start = max(0, i - win)
            seg = ys_norm[start:i]
            if len(seg) < 2:
                continue

            # 加权熵计算
            weighted_seg = seg * weights[:len(seg), None]
            ent[i] = sum(self._entropy(weighted_seg[:, j])
                         for j in range(seg.shape[1]))
        return ent

    def _bidirectional_entropy(self, ys_mat: np.ndarray, win: int) -> np.ndarray:
        """双向熵计算：正向+反向滑动窗口"""
        # 正向熵值计算
        forward_ent = self._dynamic_window(ys_mat, win)

        # 反向熵值计算（反转数据后计算）
        reversed_ys = ys_mat[::-1]
        backward_ent = self._dynamic_window(reversed_ys, win)[::-1]

        # 合并正反结果（加权平均）
        combined_ent = (forward_ent + backward_ent) / 2

        # 填充空值（用局部均值填充）
        zero_indices = np.where(combined_ent == 0)[0]
        if len(zero_indices) > 0:
            for idx in zero_indices:
                window_start = max(0, idx - win)
                window_end = min(len(combined_ent), idx + win)
                local_mean = np.mean(combined_ent[window_start:window_end])
                combined_ent[idx] = local_mean if not np.isnan(local_mean) else 0.0
        return combined_ent

    def _cluster_analysis(self, ent_series: np.ndarray) -> np.ndarray:
        """K-means聚类分析：划分高低信息量区域"""
        # 数据有效性检查
        valid_ent = ent_series[ent_series > self.min_entropy]
        if len(valid_ent) == 0:
            logger.warning("无效熵值序列，返回全零聚类标签")
            return np.zeros_like(ent_series)

        # 聚类参数配置
        cluster_params = {
            'n_clusters': self.cluster_num,
            'max_iter': self.max_iter,
            'random_state': 42
        }

        # 执行聚类
        X = valid_ent.reshape(-1, 1)
        kmeans = KMeans(**cluster_params)
        kmeans.fit(X)

        # 获取聚类中心并确定高熵簇
        centers = kmeans.cluster_centers_.flatten()
        high_cluster = np.argmax(centers)

        # 构建聚类标签掩码
        cluster_mask = np.zeros_like(ent_series)
        for i, val in enumerate(ent_series):
            if val in valid_ent:
                cluster_mask[i] = (kmeans.predict([[val]])[0] == high_cluster)
        return cluster_mask.astype(int)

    def suggest_segments_stream(
            self,
            data_dict: Dict[str, Tuple[np.ndarray, np.ndarray]],
            win: int = 300,
            k_start: int = 3,
            k_stop: int = 3,
            nan_thr: float = 0.05
    ) -> List[Tuple[str, str]]:
        """
        核心筛选算法：基于双向熵与聚类分析的状态机逻辑
        参数说明：
            data_dict: 输入数据字典 {tag_name: (ts, ys)}
            win: 滑动窗口大小
            k_start: 进入区段所需的连续高质窗口数
            k_stop: 退出区段所需的连续低质窗口数
            nan_thr: 单窗口最大缺失率阈值
        返回值：
            时间段列表 [(start_time, end_time)]
        """
        # 数据预处理
        ts = next(iter(data_dict.values()))[0]
        ys = np.vstack([v[1] for v in data_dict.values()]).T

        # 计算双向熵序列
        ent_series = self._bidirectional_entropy(ys, win)

        # 聚类分析获取高信息量掩码
        cluster_mask = self._cluster_analysis(ent_series)

        # 动态阈值计算（基于高信息量区域）
        high_ent = [ent_series[i] for i in range(len(cluster_mask))
                    if cluster_mask[i] == 1]
        if not high_ent:
            logger.warning("未检测到高信息量区域")
            return []

        t_high = np.mean(high_ent) + 0.5 * np.std(high_ent)
        t_low = np.mean(high_ent) - 1.5 * np.std(high_ent)

        # 状态机逻辑（全量遍历）
        segs = []
        state = 'OUT'
        start = None
        good_cnt = bad_cnt = 0

        for i in range(len(ts)):
            # 缺失率检查
            if np.isnan(ys[i]).mean() > nan_thr:
                continue

            # 当前窗口质量评估
            q = ent_series[i]
            is_high_info = bool(cluster_mask[i])

            if state == 'OUT':
                if q >= t_high and is_high_info:
                    good_cnt += 1
                else:
                    good_cnt = 0
                if good_cnt >= k_start:
                    start = i - k_start + 1
                    state = 'IN'
                    bad_cnt = 0
            else:  # IN_SEG
                if q <= t_low or not is_high_info:
                    bad_cnt += 1
                else:
                    bad_cnt = 0
                if bad_cnt >= k_stop:
                    end = i - k_stop + 1
                    segs.append((ts[start], ts[end]))
                    state = 'OUT'
                    good_cnt = 0

        # 处理未闭合的区段
        if state == 'IN':
            segs.append((ts[start], ts[-1]))

        logger.info(f"共检测到{len(segs)}个高信息量时间段")
        return segs

    def call(self, data: dict, win=300, k_start=3, k_stop=3, nan_thr=0.05):
        """
        对外接口方法
        参数：
            data: 输入数据字典 {tag_name: (ts: np.ndarray, ys: np.ndarray)}
            win: 滑动窗口大小
            k_start: 进入区段计数阈值
            k_stop: 退出区段计数阈值
            nan_thr: 缺失率阈值
        返回：
            高信息量时间段列表
        """
        return self.suggest_segments_stream(data, win, k_start, k_stop, nan_thr)
