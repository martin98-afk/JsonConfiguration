"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: jenks_breakpoint.py
@time: 2025/6/23 08:48
@desc: 
"""
import numpy as np

from typing import Dict, Tuple
from jenkspy import jenks_breaks
from kneed import KneeLocator
from loguru import logger
from matplotlib import pyplot as plt

from application.base import BaseTool


class JenksBreakpoint(BaseTool):
    """
    自动计算最佳jenks breakpoint
    """

    def __init__(self, **kwargs):
        super().__init__()
        pass

    def find_optimal_jenks(
            self, data: np.ndarray,
            max_k: int = 10,
            sample_size: int = 10000,
            use_auto_knee: bool = True,
            return_plot: bool = False,
            random_seed: int = 42
    ) -> Tuple[int, Dict, np.ndarray, plt.Figure]:
        """
        自动确定Jenks自然间断点法的最佳分类数

        参数：
        data : 输入数据数组
        max_k : 考虑的最大分类数（默认10）
        use_auto_knee : 是否使用Kneed算法自动检测拐点（默认True）
        sample_size: 随机采样数
        random_seed: 随机种子
        return_plot : 是否返回可视化图表（默认False）

        返回：
        best_k : 推荐的最佳分类数
        metrics : 包含评估指标的字典
        breaks : 最佳分类对应的间断点数组
        fig : 可视化图表对象（仅当return_plot=True时返回）
        """
        # 参数校验
        if not isinstance(data, np.ndarray):
            data = np.array(data)
        if max_k < 2:
            raise ValueError("max_k必须大于等于2")
        if len(data) < max_k:
            raise ValueError("数据量必须大于max_k")

        # 数据预处理
        orig_data = np.asarray(data).ravel()
        n = len(orig_data)

        # 智能数据抽样（保留分布特征）
        if n > sample_size:
            np.random.seed(random_seed)
            stratify_bins = min(100, n // 100)  # 动态分层数
            bins = np.linspace(orig_data.min(), orig_data.max(), stratify_bins)
            digitized = np.digitize(orig_data, bins)

            # 分层随机抽样
            sampled_indices = []
            for d in np.unique(digitized):
                pool = np.where(digitized == d)[0]
                if len(pool) == 0: continue
                sample_num = min(max(1, int(sample_size * len(pool) / n)), len(pool))
                sampled_indices.extend(np.random.choice(pool, sample_num, replace=False))
            logger.info(f"数据量超过{sample_size}，进行智能采样采样长度: {len(sampled_indices)}")
            # 确保抽样总数不超过目标
            sampled_data = orig_data[sampled_indices]
            logger.info(f"数据量从 {n} 抽样至 {sample_size}（分层抽样）")
        else:
            sampled_data = orig_data.copy()

        # 初始化指标存储
        k_values = list(range(2, max_k + 1))
        metrics = {
            'gvf': [],
            'bic': [],
            'f_stat': [],
            'breaks_list': []
        }

        # 计算总方差
        mean = np.mean(sampled_data)
        sst = np.sum((sampled_data - mean) ** 2)
        n = len(sampled_data)

        # 遍历所有k值
        for i, k in enumerate(k_values):
            # 计算自然间断点
            breaks = jenks_breaks(sampled_data, n_classes=k)
            metrics['breaks_list'].append(breaks)

            # 计算组内方差
            classes = np.digitize(sampled_data, breaks[1:-1])  # 排除首尾断点
            ssw = 0
            for i in range(k):
                class_data = sampled_data[classes == i]
                if len(class_data) > 0:
                    ssw += np.sum((class_data - np.mean(class_data)) ** 2)

            # 计算评估指标
            gvf = (sst - ssw) / sst
            metrics['gvf'].append(gvf)

            # 伪F统计量
            f_stat = ((sst - ssw) / (k - 1)) / (ssw / (n - k)) if k > 1 else 0
            metrics['f_stat'].append(f_stat)

            # BIC
            bic = n * np.log(ssw / n) + k * np.log(n)
            metrics['bic'].append(bic)

        # 自动选择最佳k值
        if use_auto_knee:
            # 使用Kneed算法检测GVF曲线拐点
            kneedle = KneeLocator(k_values, metrics['gvf'], curve='concave', direction='increasing', S=2)
            best_k = kneedle.knee if kneedle.knee else k_values[-1]
        else:
            # 使用BIC最小值
            best_k = k_values[np.argmin(metrics['bic'])]

        # 获取最佳断点
        best_breaks = metrics['breaks_list'][best_k - 2]  # k从2开始

        # 可视化
        fig = None
        if return_plot:
            fig = plt.figure(figsize=(12, 5))

            # GVF曲线
            plt.subplot(1, 2, 1)
            plt.plot(k_values, metrics['gvf'], 'bo-')
            plt.axvline(best_k, color='r', linestyle='--')
            plt.xlabel('Number of classes (k)')
            plt.ylabel('GVF')
            plt.title(f'Best k={best_k} (Auto)')

            # 数据分布
            plt.subplot(1, 2, 2)
            plt.hist(data, bins=30, alpha=0.7)
            for b in best_breaks:
                plt.axvline(b, color='r', linestyle='--')
            plt.title('Data Distribution with Breaks')

            plt.tight_layout()

        return (best_k, metrics, best_breaks, fig) if return_plot else (best_k, metrics, best_breaks)

    def call(self, data: np.ndarray):

        # 对每个工况进行Jenks自然间断点聚类
        n_class = 10
        n_class = min(n_class, len(set(data)))
        if len(set(data)) <= 5: return []
        # 使用Jenks自然间断点算法
        best_k, metrics, best_breaks = self.find_optimal_jenks(data=data, max_k=n_class, return_plot=False)

        return best_breaks