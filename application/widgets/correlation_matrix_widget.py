"""相关系数矩阵绘制组件

此组件为趋势分析对话框提供相关系数矩阵的可视化功能。
包括热图绘制、颜色映射选择和样式控制等功能。
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QFrame,
    QScrollArea,
)


class CorrelationMatrixWidget(QWidget):
    """相关系数矩阵显示组件"""

    # 定义信号
    matrixUpdated = pyqtSignal(dict)  # 矩阵更新信号
    cellSelected = pyqtSignal(str, str, float)  # 单元格选择信号 (行名称, 列名称, 值)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 配置
        self.colormap = "coolwarm"  # 默认颜色映射
        self.threshold = 0.7  # 高相关性阈值
        self.compact_mode = True  # 默认使用紧凑模式
        self.names = []  # 测点名称列表
        self.corr_matrix = None  # 相关系数矩阵

        # UI初始化
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 添加一个滚动区域，使大型矩阵可以通过滚动查看
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet(
            """
            QScrollArea { 
                background: transparent; 
                border: none; 
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                border: none;
                background: #f8f9fa;
                width: 10px;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #adb5bd;
                border-radius: 5px;
                min-height: 30px;
                min-width: 30px;
            }
        """
        )

        # 控制区域
        control_frame = QFrame()
        control_frame.setObjectName("controlFrame")
        control_frame.setStyleSheet(
            """
            #controlFrame {
                background-color: #f8f9fa;
                border-radius: 4px;
                border: 1px solid #e9ecef;
            }
        """
        )
        # 矩阵显示区域 - 使用自适应大小的Figure
        # 基础大小为8x7，但会根据测点数量动态调整
        self.figure = Figure(figsize=(8, 7), dpi=100, facecolor="white")
        self.canvas = FigureCanvas(self.figure)

        # 创建一个容器小部件用于放置在滚动区域中
        canvas_container = QWidget()
        canvas_container_layout = QVBoxLayout(canvas_container)
        canvas_container_layout.setContentsMargins(0, 0, 0, 0)
        canvas_container_layout.addWidget(self.canvas)
        canvas_container_layout.setAlignment(Qt.AlignCenter)
        # 将容器放入滚动区域
        self.scroll_area.setWidget(canvas_container)
        layout.addWidget(self.scroll_area, 1)  # 占据剩余空间

        # 信息区域
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(5, 0, 5, 0)

        self.info_label = QLabel("请提供数据来生成相关系数矩阵")
        self.info_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        info_layout.addWidget(self.info_label)

        info_layout.addStretch()

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        info_layout.addWidget(self.stats_label)

        layout.addLayout(info_layout)

    def _on_colormap_changed(self, index):
        """颜色映射变化处理"""
        self.colormap = self.colormap_combo.currentText()
        self._update_plot()

    def _on_threshold_changed(self, index):
        """相关阈值变化处理"""
        self.threshold = float(self.threshold_combo.currentText())
        self._update_plot()

    def set_data(self, data_dict):
        """设置数据并计算相关系数矩阵

        Args:
            data_dict: 测点数据字典 {测点名称: 数据数组}
        """
        if not data_dict or len(data_dict) < 2:
            self.info_label.setText("需要至少两个测点才能计算相关系数矩阵")
            self.figure.clear()
            self.canvas.draw()
            return False

        try:
            # 提取名称和数据
            self.names = list(data_dict.keys())
            data_arrays = list(data_dict.values())

            # 确保所有数据长度一致，取最小长度
            min_length = min(len(arr) for arr in data_arrays)
            data_arrays = [arr[:min_length] for arr in data_arrays]

            # 计算相关系数矩阵
            self.corr_matrix = np.corrcoef(data_arrays)

            # 更新信息
            self.info_label.setText(f"已计算 {len(self.names)} 个测点的相关系数矩阵")
            self.stats_label.setText(f"数据点数: {min_length}")

            # 更新图表
            self._update_plot()
            return True
        except Exception as e:
            self.info_label.setText(f"计算相关系数时出错: {str(e)}")
            self.figure.clear()
            self.canvas.draw()
            return False

    def _update_plot(self):
        """更新相关系数矩阵图表"""
        if self.corr_matrix is None or len(self.names) == 0:
            return

        # 根据测点数量动态调整图表大小
        n_points = len(self.names)
        if self.compact_mode:
            width = max(10, 10 + (n_points - 10) * 0.25) if n_points > 10 else 10
            height = max(9, 9 + (n_points - 10) * 0.25) if n_points > 10 else 9
        else:
            width = max(8, 8 + (n_points - 10) * 0.12) if n_points > 10 else 8
            height = max(7, 7 + (n_points - 10) * 0.12) if n_points > 10 else 7
        self.figure.set_size_inches(width, height)

        # 清除当前图表
        self.figure.clear()

        # 创建子图
        ax = self.figure.add_subplot(111)

        # 动态调整字体大小和标签旋转角度
        n_points = len(self.names)
        if self.compact_mode:
            label_fontsize = max(6, 10 - n_points // 10)  # 根据测点数量动态调整
            value_fontsize = max(5, 9 - n_points // 10)
        else:
            label_fontsize = max(8, 12 - n_points // 8)
            value_fontsize = max(7, 10 - n_points // 8)

        # 处理 NaN 值
        corr_matrix_with_nan = np.where(np.isnan(self.corr_matrix), np.nan, self.corr_matrix)
        corr_matrix_display = np.nan_to_num(corr_matrix_with_nan, nan=-2)  # 将 NaN 替换为 -2

        # 绘制热图
        cax = ax.matshow(corr_matrix_display, cmap=self.colormap, vmin=-1, vmax=1)

        # 添加颜色条
        cbar = self.figure.colorbar(cax)
        cbar.set_label("相关系数", fontsize=label_fontsize + 1)
        cbar.ax.tick_params(labelsize=label_fontsize - 1)

        # 在颜色条中标注 NaN
        cbar.ax.text(
            0.5, -0.05, "NaN", ha="center", va="center", fontsize=label_fontsize, color="gray"
        )

        # 设置坐标轴标签
        ax.set_xticks(np.arange(len(self.names)))
        ax.set_yticks(np.arange(len(self.names)))
        ax.set_xticklabels(self.names)
        ax.set_yticklabels(self.names)

        # 确保标签居中对齐
        plt.setp(ax.get_xticklabels(), ha="center")
        plt.setp(ax.get_yticklabels(), va="center")

        # 调整字体大小
        ax.tick_params(axis="both", labelsize=label_fontsize)
        ax.tick_params(axis="x", rotation=45)

        # 在每个单元格中显示相关系数值
        threshold = self.threshold  # 高相关阈值
        for i in range(len(self.names)):
            for j in range(len(self.names)):
                value = corr_matrix_with_nan[i, j]  # 使用原始矩阵中的值

                # 确定是否显示此值 - 紧凑模式下也始终显示主要相关值
                if (
                    abs(value) < threshold
                    and i != j
                    and self.compact_mode == False
                ):
                    continue

                # 确定颜色和字体
                if np.isnan(value):  # 如果是 NaN，特殊处理
                    color = "white"  # 使用白色字体
                    weight = "bold"
                    fontsize = value_fontsize + 1
                    text = "NaN"
                    # 设置灰色背景
                    ax.add_patch(
                        plt.Rectangle(
                            (j - 0.5, i - 0.5),
                            1,
                            1,
                            fill=True,
                            color="gray",
                            alpha=0.5,
                            zorder=0,
                        )
                    )
                elif abs(value) >= threshold:
                    color = "white"
                    weight = "bold"
                    fontsize = value_fontsize + 1
                    text = f"{value:.2f}"
                else:
                    color = "black" if abs(value) < 0.5 else "white"
                    weight = "normal"
                    fontsize = value_fontsize
                    text = f"{value:.2f}"

                # 对角线元素特殊处理
                if i == j:
                    weight = "bold"
                    fontsize = value_fontsize + 1
                    color = "white"  # 确保对角线元素使用白色字体更醒目

                # 文本对齐方式根据模式来确定
                text_align = "center" if not self.compact_mode else "center"
                ax.text(
                    j,
                    i,
                    text,
                    ha=text_align,
                    va="center",
                    color=color,
                    fontweight=weight,
                    fontsize=fontsize,
                )

        # 优化网格线
        ax.grid(which="minor", color="w", linestyle="-", linewidth=0.5)
        ax.set_xticks(np.arange(-0.5, len(self.names), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(self.names), 1), minor=True)

        # 设置背景色
        ax.set_facecolor("#f8f9fa")

        # 调整布局，确保在大矩阵情况下能够完整显示
        self.figure.tight_layout(pad=8)

        # 动态调整 FigureCanvas 的最小尺寸，确保滚动区域能够完全显示整个矩阵
        self.canvas.setMinimumHeight(60 * n_points)  # 增加高度比例
        self.canvas.setMinimumWidth(60 * n_points)   # 增加宽度比例

        # 修改: 强制更新滚动区域的几何属性
        self.scroll_area.updateGeometry()
        self.scroll_area.ensureWidgetVisible(self.canvas)

        # 绘制图表
        self.canvas.draw()

        # 发送矩阵更新信号
        corr_data = {}
        for i, name_i in enumerate(self.names):
            corr_data[name_i] = {}
            for j, name_j in enumerate(self.names):
                corr_data[name_i][name_j] = self.corr_matrix[i, j]
        self.matrixUpdated.emit(corr_data)

    def clear(self):
        """清除图表"""
        self.names = []
        self.corr_matrix = None
        self.figure.clear()
        self.canvas.draw()
        self.info_label.setText("请提供数据来生成相关系数矩阵")
        self.stats_label.setText("")

    def sizeHint(self):
        """提供推荐尺寸"""
        return QSize(700, 550)

    def minimumSizeHint(self):
        """提供最小尺寸"""
        return QSize(400, 300)
