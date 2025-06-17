import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from loguru import logger
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QComboBox, QFrame, QScrollArea, QSizePolicy, QCheckBox)

class HistogramWidget(QWidget):
    """改进的直方图控件，支持固定分页和多种图表类型"""

    # 信号定义
    histogramUpdated = pyqtSignal()  # 直方图更新完成信号

    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置基本属性
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 配置参数
        self.hist_type = 0  # 0:标准直方图, 1:核密度估计, 2:组合显示
        self.color_theme = 0  # 0:蓝色, 1:彩虹, 2:绿色, 3:暖色
        self.bin_count = 'auto'  # 柱状图区间数量
        self.data_dict = {}  # 数据字典 {名称: (时间序列,值序列)}
        self.current_page = 0  # 当前页码
        self.items_per_page = 4  # 每页固定显示4个图表
        self.statistics = {}  # 统计信息缓存
        self.show_stats = True  # 是否显示统计信息

        # 初始化UI
        self._init_ui()

    def _init_ui(self):
        """初始化用户界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        # 顶部控制面板
        control_frame = QFrame()
        control_frame.setStyleSheet("""
            QFrame {
                background-color: #f1f8ff;
                border-radius: 4px;
                margin-bottom: 5px;
                padding: 5px;
            }
        """)
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(10, 5, 10, 5)

        # 标题标签
        title = QLabel("频数分布直方图")
        title.setStyleSheet("font-weight: bold; color: #1864ab; font-size: 13px;")
        control_layout.addWidget(title)

        # 添加分页控制
        pagination_frame = QFrame()
        pagination_frame.setMaximumHeight(40)
        pagination_frame.setStyleSheet(
            """
                    QFrame {
                        background-color: #e7f5ff;
                        border-radius: 4px;
                    }
                """
        )

        page_label = QLabel("页码:")
        page_label.setStyleSheet("color: #495057; font-size: 12px;")
        control_layout.addWidget(page_label)

        self.page_combo = QComboBox()
        self.page_combo.setStyleSheet(
            """
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 5px;
                min-width: 100px;
                font-size: 11px;
                background-color: white;
                color: black; /* 默认字体颜色 */
            }
            QComboBox:hover {
                border-color: #40a9ff;
                color: black; /* 鼠标悬浮时字体颜色 */
            }"""
        )
        self.page_combo.currentIndexChanged.connect(self._on_page_changed)
        control_layout.addWidget(self.page_combo)

        control_layout.addStretch()

        # 直方图类型选择
        type_label = QLabel("图表类型:")
        type_label.setStyleSheet("color: #495057; font-size: 12px;")
        control_layout.addWidget(type_label)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["标准直方图", "核密度估计", "组合显示"])
        self.type_combo.setCurrentIndex(0)  # 默认选择组合显示
        self.type_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 5px;
                min-width: 100px;
                font-size: 11px;
                background-color: white;
                color: black; /* 默认字体颜色 */
            }
            QComboBox:hover {
                border-color: #40a9ff;
                color: black; /* 鼠标悬浮时字体颜色 */
            }
        """)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        control_layout.addWidget(self.type_combo)

        # 颜色主题选择
        color_label = QLabel("颜色主题:")
        color_label.setStyleSheet("color: #495057; font-size: 12px;")
        control_layout.addWidget(color_label)

        self.color_combo = QComboBox()
        self.color_combo.addItems(["蓝色", "彩虹", "绿色", "暖色"])
        self.color_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 5px;
                min-width: 100px;
                font-size: 11px;
                background-color: white;
                color: black; /* 默认字体颜色 */
            }
            QComboBox:hover {
                border-color: #40a9ff;
                color: black; /* 鼠标悬浮时字体颜色 */
            }
        """)
        self.color_combo.currentIndexChanged.connect(self._on_color_changed)
        control_layout.addWidget(self.color_combo)

        # 区间数量控制
        bins_label = QLabel("区间数:")
        bins_label.setStyleSheet("color: #495057; font-size: 12px; margin-left: 5px;")
        control_layout.addWidget(bins_label)

        self.bins_combo = QComboBox()
        self.bins_combo.addItems(["自动", "10", "20", "30", "50"])
        self.bins_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 5px;
                min-width: 100px;
                font-size: 11px;
                background-color: white;
                color: black; /* 默认字体颜色 */
            }
            QComboBox:hover {
                border-color: #40a9ff;
                color: black; /* 鼠标悬浮时字体颜色 */
            }
        """)
        self.bins_combo.currentIndexChanged.connect(self._on_bins_changed)
        control_layout.addWidget(self.bins_combo)

        # 统计信息显示设置
        stats_label = QLabel("统计信息:")
        stats_label.setStyleSheet("color: #495057; font-size: 12px;")
        control_layout.addWidget(stats_label)

        # 新增复选框
        self.stats_checkbox = QCheckBox("")
        self.stats_checkbox.setChecked(True)  # 默认显示统计信息
        self.stats_checkbox.setStyleSheet("""
            QCheckBox {
                color: #495057;
                font-size: 11px;
            }
        """)
        self.stats_checkbox.stateChanged.connect(self._on_stats_changed)
        control_layout.addWidget(self.stats_checkbox)

        main_layout.addWidget(control_frame)

        main_layout.addWidget(pagination_frame)

        # 添加滚动区域用于显示图表
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #f8f9fa;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #adb5bd;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #868e96;
            }
        """)

        # 创建图表容器
        self.container = QWidget()
        self.container.setStyleSheet("background-color: white;")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(10, 10, 10, 10)
        self.container_layout.setSpacing(15)

        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area, 1)  # 1是伸缩因子

        # 状态区域
        status_frame = QFrame()
        status_frame.setMaximumHeight(30)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 0, 10, 0)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        # 数据信息标签
        self.data_info_label = QLabel("无数据")
        self.data_info_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        status_layout.addWidget(self.data_info_label)

        main_layout.addWidget(status_frame)

        # 初始状态下显示无数据提示
        self._show_no_data_message()

    def _on_type_changed(self, index):
        """处理直方图类型变更"""
        self.hist_type = index
        self.status_label.setText(f"已切换到{self.type_combo.currentText()}")
        # 如果有数据则更新直方图
        if self.data_dict:
            self._update_histograms()

    def _on_color_changed(self, index):
        """处理颜色主题变更"""
        self.color_theme = index
        self.status_label.setText(f"已切换到{self.color_combo.currentText()}主题")
        # 如果有数据则更新直方图
        if self.data_dict:
            self._update_histograms()

    def _on_bins_changed(self, index):
        """处理区间数量变更"""
        if index == 0:
            self.bin_count = 'auto'
        else:
            self.bin_count = int(self.bins_combo.currentText())
        self.status_label.setText(f"已设置区间数为{self.bins_combo.currentText()}")
        # 如果有数据则更新直方图
        if self.data_dict:
            self._update_histograms()

    def _on_stats_changed(self, state):
        """处理统计信息显示设置变更"""
        self.show_stats = (state == Qt.Checked)  # 复选框选中表示显示统计信息
        self.status_label.setText(f"{'显示' if self.show_stats else '隐藏'}统计信息")
        # 如果有数据则更新直方图
        if self.data_dict:
            self._update_histograms()

    def _on_page_changed(self, index):
        """处理页码变更"""
        self.current_page = index
        self.status_label.setText(f"已切换到第{index + 1}页")
        # 更新直方图显示
        if self.data_dict:
            self._update_histograms()

    def set_data(self, data_dict):
        """设置要显示的数据

        Args:
            data_dict: 数据字典，格式为 {名称: (时间序列, 值序列)}
        """
        # 检查数据有效性
        valid_data = {}
        for name, (ts, ys) in data_dict.items():
            if ts is not None and len(ts) > 0 and len(ys) > 0:
                valid_data[name] = (ts, ys)

        if not valid_data:
            self._show_no_data_message()
            return

        # 保存有效数据
        self.data_dict = valid_data
        n_points = len(valid_data)

        # 计算总页数
        total_pages = (n_points + self.items_per_page - 1) // self.items_per_page

        # 更新页码选择框
        self.page_combo.blockSignals(True)  # 阻止信号以避免触发更新
        self.page_combo.clear()
        for i in range(total_pages):
            self.page_combo.addItem(f"{i+1}/{total_pages}")

        # 如果当前页超出范围，重置为第一页
        if self.current_page >= total_pages:
            self.current_page = 0
        self.page_combo.setCurrentIndex(self.current_page)
        self.page_combo.blockSignals(False)  # 恢复信号

        # 更新数据信息标签
        total_points = sum(len(ys) for _, (_, ys) in valid_data.items())
        self.data_info_label.setText(f"样本数量: {total_points}")

        # 计算统计信息
        self._calculate_statistics()

        # 更新直方图
        self._update_histograms()

        # 更新状态
        self.status_label.setText(f"测点数量: {n_points}")

    def _calculate_statistics(self):
        """计算并缓存每个测点的统计信息"""
        self.statistics = {}

        for name, (_, ys) in self.data_dict.items():
            if len(ys) == 0:
                continue

            # 计算基本统计量
            stats = {
                'mean': np.mean(ys),
                'median': np.median(ys),
                'std': np.std(ys),
                'min': np.min(ys),
                'max': np.max(ys),
                'count': len(ys)
            }

            # 添加分位数
            try:
                stats['q1'] = np.percentile(ys, 25)  # 第一四分位数
                stats['q3'] = np.percentile(ys, 75)  # 第三四分位数
                stats['iqr'] = stats['q3'] - stats['q1']  # 四分位距
            except:
                stats['q1'] = stats['q3'] = stats['iqr'] = float('nan')

            # 识别异常值
            try:
                lower_bound = stats['q1'] - 1.5 * stats['iqr']
                upper_bound = stats['q3'] + 1.5 * stats['iqr']
                outliers = [y for y in ys if y < lower_bound or y > upper_bound]
                stats['outliers_count'] = len(outliers)
                stats['outliers_percent'] = (len(outliers) / len(ys)) * 100 if len(ys) > 0 else 0
            except:
                stats['outliers_count'] = stats['outliers_percent'] = float('nan')

            self.statistics[name] = stats

    def _update_histograms(self):
        """更新直方图显示"""
        # 清除当前容器中的所有部件
        for i in reversed(range(self.container_layout.count())):
            widget = self.container_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # 获取当前页的数据
        data_items = list(self.data_dict.items())
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(data_items))
        current_page_data = data_items[start_idx:end_idx]

        if not current_page_data:
            self._show_no_data_message()
            return

        # 使用固定的2x2布局（即使不足4个也用这个布局保持一致性）
        n_rows = 2
        n_cols = 2

        # 创建大小合适的Figure，减小高度比例缓解重叠问题
        figure = Figure(figsize=(10, 7.5), dpi=100, facecolor='white')
        figure.patch.set_alpha(0.0)  # 设置透明背景
        # 增加子图上下边距，为标题和轴标签留出空间
        figure.subplots_adjust(top=0.88, bottom=0.1)

        # 获取当前选择的颜色主题
        color_themes = {
            0: '#1c7ed6',   # 蓝色主题
            1: 'rainbow',   # 彩虹主题
            2: '#2b8a3e',   # 绿色主题
            3: '#e67700'    # 暖色主题
        }
        current_color = color_themes.get(self.color_theme, '#1c7ed6')

        # 计算并绘制各个直方图
        for idx, (name, (ts, ys)) in enumerate(current_page_data):
            if len(ys) == 0:
                continue

            # 创建子图，2x2布局，即使不足4个也保持这个布局
            ax = figure.add_subplot(n_rows, n_cols, idx + 1)

            # 计算合适的柱状图数量
            if self.bin_count == 'auto':
                # 使用Sturges规则
                n_bins = int(np.ceil(np.log2(len(ys)) + 1))
                n_bins = max(10, min(30, n_bins))  # 最少10个，最多30个区间
            else:
                n_bins = self.bin_count

            # 使用选定的颜色
            if self.color_theme == 1:  # 彩虹主题
                color_map = plt.cm.rainbow
                histogram_color = color_map(idx / max(1, len(self.data_dict) - 1))
            else:
                histogram_color = current_color

            # 根据选择的直方图类型进行绘制
            if self.hist_type == 0 or self.hist_type == 2:  # 标准直方图或组合显示
                n, bins, patches = ax.hist(ys, bins=n_bins, alpha=0.7, color=histogram_color, 
                                         density=True, edgecolor='white', linewidth=0.8)

            # 绘制核密度估计曲线
            if self.hist_type == 1 or self.hist_type == 2:  # 核密度估计或组合显示
                try:
                    from scipy.stats import gaussian_kde
                    kde = gaussian_kde(ys)
                    x_range = np.linspace(min(ys), max(ys), 1000)
                    # 核密度曲线使用红色
                    ax.plot(x_range, kde(x_range), 'r-', linewidth=2)
                except Exception as e:
                    logger.error(f"核密度估计失败: {e}")

            # 设置标题和轴标签
            ax.set_title(name, fontsize=12, fontweight='bold', pad=15)  # 增加标题和图表间的距离
            ax.set_ylabel('频率', fontsize=10)

            # 优化网格线
            ax.grid(True, linestyle='--', alpha=0.3, color='#adb5bd')

            # 设置背景色
            ax.set_facecolor('#f8f9fa')

            # 去除上边框和右边框
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_linewidth(0.5)
            ax.spines['bottom'].set_linewidth(0.5)
            ax.spines['left'].set_color('#adb5bd')
            ax.spines['bottom'].set_color('#adb5bd')

            # 如果启用统计信息，则显示统计面板
            if self.show_stats and name in self.statistics:
                stats = self.statistics[name]

                # 创建统计信息文本
                stats_text = (
                    f"均值: {stats['mean']:.2f}\n"
                    f"中位数: {stats['median']:.2f}\n"
                    f"标准差: {stats['std']:.2f}\n"
                    f"最小值: {stats['min']:.2f}\n"
                    f"最大值: {stats['max']:.2f}\n"
                    f"数据量: {stats['count']}"
                )

                # 使用文本框展示统计信息，放在右上角而不是左上角，避免遮挡直方图
                ax.text(0.98, 0.98, stats_text, transform=ax.transAxes, 
                       verticalalignment='top', horizontalalignment='right', fontsize=9,
                       bbox={'boxstyle': 'round,pad=0.5', 'facecolor': 'white', 
                             'alpha': 0.9, 'edgecolor': '#ced4da'})

        # 调整子图间距，避免重叠
        figure.subplots_adjust(hspace=0.9, wspace=0.3)  # 增大垂直间距解决标题重叠问题

        # 创建并添加画布
        canvas = FigureCanvas(figure)
        self.container_layout.addWidget(canvas)

        # 发送信号表示直方图已更新
        self.histogramUpdated.emit()

    def _show_no_data_message(self):
        """显示无数据提示"""
        # 清除当前容器中的所有部件
        for i in reversed(range(self.container_layout.count())):
            widget = self.container_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # 创建提示信息框
        no_data_label = QLabel("没有可用的数据进行分析。请选择测点并获取数据。")
        no_data_label.setAlignment(Qt.AlignCenter)
        no_data_label.setStyleSheet("""
            color: #6c757d; 
            font-size: 14px; 
            padding: 50px;
            background-color: #f8f9fa;
            border: 1px dashed #ced4da;
            border-radius: 8px;
        """)
        self.container_layout.addWidget(no_data_label)

    def clear(self):
        """清除所有数据和图表"""
        self.data_dict = {}
        self.statistics = {}
        self.current_page = 0

        # 重置页码选择器
        self.page_combo.blockSignals(True)
        self.page_combo.clear()
        self.page_combo.blockSignals(False)

        # 更新标签
        self.data_info_label.setText("无数据")
        self.status_label.setText("已清除所有数据")

        # 显示无数据提示
        self._show_no_data_message()

    def sizeHint(self):
        """返回推荐的部件尺寸"""
        return QSize(800, 600)

    def minimumSizeHint(self):
        """返回最小建议尺寸"""
        return QSize(400, 300)
