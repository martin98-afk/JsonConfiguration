"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: calc_normal_range.py
@time: 2025/6/27 09:06
@desc: 
"""
import numpy as np

from sklearn.mixture import GaussianMixture
from application.base import BaseTool


class CalcNormalRange(BaseTool):
    """
    自动寻找信息量高的训练区间（支持多测点，滑窗判断）
    包含双向熵计算、K-means聚类、动态阈值调整等核心功能
    """

    def __init__(self):
        """初始化参数配置"""
        super().__init__()

    def _robust_range(self, data, n_components=3, std_scale=3, weight_threshold=0.05):
        data = np.asarray(data).reshape(-1, 1)

        # 判断离散变量
        unique_values = np.unique(data)
        if len(unique_values) <= 10:
            return [float(data.min()), float(data.max())]

        # 拟合 GMM 模型（增强稳定性）
        gmm = GaussianMixture(
            n_components=n_components,
            random_state=0,
            max_iter=100,
            n_init=10  # 多次初始化以选择最优解
        )
        gmm.fit(data)

        # 提取有效成分（排除权重过小的成分）
        valid_components = [
            (mean[0], std[0][0])
            for weight, mean, std in zip(gmm.weights_, gmm.means_, np.sqrt(gmm.covariances_))
            if weight >= weight_threshold
        ]

        # 计算全局动态范围
        if valid_components:
            lower = min(mean - std_scale * std for mean, std in valid_components)
            upper = max(mean + std_scale * std for mean, std in valid_components)
        else:
            lower = float(data.min())
            upper = float(data.max())

        # 裁剪数据
        trimmed = data[(data >= lower) & (data <= upper)]
        if trimmed.size == 0:
            trimmed = data

        return [float(trimmed.min()), float(trimmed.max())]

    def call(self, data: np.array, n_components=3, std_scale=3, weight_threshold=0.05):
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
        return self._robust_range(data, n_components, std_scale, weight_threshold)