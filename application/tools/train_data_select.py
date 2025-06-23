"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: train_data_select.py
@time: 2025/6/23 15:54
@desc: 
"""
from datetime import datetime
from typing import Tuple, Dict, List

import numpy as np
from sklearn.preprocessing import MinMaxScaler

from application.base import BaseTool


class TrainDataSelect(BaseTool):
    """
    自动寻找信息量高的训练区间（支持多测点，滑窗判断）
    """

    def __init__(self):
        """
        :param sample_size: 每段最小长度
        :param win: 计算信息量的滑窗大小
        :param k_start: 进入区段前的连续高质量窗口数
        :param k_stop: 退出区段前的连续低质量窗口数
        :param nan_thr: 单窗口最大缺失率（超过视为无效）
        """
        super().__init__()

    def _entropy(self, col, bins=10):
        hist, _ = np.histogram(col, bins=bins, density=True)
        hist = hist[hist > 0]
        p = hist / hist.sum()  # ← 归一化成概率
        return -np.sum(p * np.log2(p))  # ≥ 0

    def _rolling_entropy(self, ys_mat: np.ndarray, win: int) -> np.ndarray:
        scaler = MinMaxScaler()
        ys_norm = scaler.fit_transform(ys_mat)
        ent = np.zeros(len(ys_mat))
        for i in range(win, len(ys_mat)):
            seg = ys_norm[i - win:i]
            ent[i] = sum(self._entropy(seg[:, j]) for j in range(seg.shape[1]))
        return ent

    def suggest_segments_stream(
            self, data_dict: Dict[str, Tuple[np.ndarray, np.ndarray]],
            win: int = 300,
            k_start: int = 3,
            k_stop: int = 3,
            nan_thr: float = 0.05
    ) -> List[Tuple[str, str]]:
        ts = next(iter(data_dict.values()))[0]
        ys = np.vstack([v[1] for v in data_dict.values()]).T

        ent_series = self._rolling_entropy(ys, win)

        # 计算阈值：70% 和 30% 分位
        valid_ent = ent_series[ent_series > 0]
        if len(valid_ent) == 0:
            return []

        t_high = np.percentile(valid_ent, 70)
        t_low = np.percentile(valid_ent, 30)

        segs = []
        state = 'OUT'
        start = None
        good_cnt = bad_cnt = 0

        for i in range(win, len(ts)):
            q = [i]
            if np.isnan(ys[i]).mean() > nan_thr:
                q = 0

            if state == 'OUT':
                good_cnt = good_cnt + 1 if q >= t_high else 0
                if good_cnt >= k_start:
                    start = i - k_start + 1
                    state = 'IN'
                    bad_cnt = 0
            else:  # IN_SEG
                bad_cnt = bad_cnt + 1 if q <= t_low else 0
                if bad_cnt >= k_stop:
                    end = i - k_stop + 1
                    segs.append((ts[start], ts[end]))
                    state = 'OUT'
                    good_cnt = 0

        if state == 'IN':
            segs.append((ts[start], ts[-1]))

        return segs

    def call(self, data: dict, win=300, k_start=3, k_stop=3, nan_thr=0.05):
        """
        :param data: {tag_name: (ts: np.ndarray, ys: np.ndarray)}
        :return: List[Tuple[start_time_str, end_time_str]]
        """
        return self.suggest_segments_stream(data, win, k_start, k_stop, nan_thr)
