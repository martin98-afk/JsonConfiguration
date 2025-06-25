import re
import numpy as np
import numpy as np
import pyqtgraph as pg

from typing import List
from sklearn.mixture import GaussianMixture
from PyQt5.QtCore import Qt, QDateTime, QThreadPool, QTimer, QPoint
from PyQt5.QtWidgets import (
    QDialog, QApplication, QVBoxLayout, QHBoxLayout,
    QPushButton, QDateTimeEdit, QLabel, QDoubleSpinBox, QComboBox, QMenu, QToolTip
)

from application.tools.jenks_breakpoint import JenksBreakpoint
from application.utils.threading_utils import Worker
from application.utils.utils import styled_dt, get_icon, get_button_style_sheet
from application.widgets.draggable_lines import DraggableLine
from application.widgets.histogram_plot_widget import HistogramPlotWidget


class IntervalPartitionDialog(QDialog):
    """
    - 仅在划分模式下响应点击新增断点
    - 拖拽断点时不会再触发新增
    - 动态连接/断开 sigMouseClicked
    """

    def __init__(self, dfs, point_name: str, current_text: str = "", type: str = "range", parent=None):
        super().__init__(parent)
        if type not in {"range", "partition"}:
            raise ValueError("type must be 'range' or 'partition'")

        self.type = type
        self.dfs = dfs
        self.point_name = point_name
        self.cut_lines: List[DraggableLine] = []
        self.bar_item = None
        self.current_data: np.ndarray | None = None  # 最近一次载入的 y 值
        self.thread_pool = QThreadPool.globalInstance()

        self.setWindowTitle("划分区间")
        self.resize(1200, 650)

        self._build_ui()
        self._init_time_range()
        QTimer.singleShot(0, self.update_histogram_async)

        if current_text:
            self._restore_breakpoints(current_text)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        ctrl = QHBoxLayout()

        # 时间范围
        ctrl.addWidget(QLabel('开始:'))
        self.start_dt = styled_dt(QDateTimeEdit(calendarPopup=True))
        ctrl.addWidget(self.start_dt)
        ctrl.addWidget(QLabel('结束:'))
        self.end_dt = styled_dt(QDateTimeEdit(calendarPopup=True))
        ctrl.addWidget(self.end_dt)

        # 采样数
        ctrl.addWidget(QLabel('采样数:'))
        self.cmb_sample = QComboBox(self)
        for v in (600, 2000, 5000):
            self.cmb_sample.addItem(str(v), v)
        self.cmb_sample.setCurrentIndex(1)
        self.cmb_sample.setStyleSheet(
            """
            QComboBox {
                padding: 4px 8px;
                border: 1px solid #1890ff;
                border-radius: 4px;
                background-color: white;
                color: black; /* 默认字体颜色 */
            }
            QComboBox:hover {
                border-color: #40a9ff;
                color: black; /* 鼠标悬浮时字体颜色 */
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border-left: none;
            }
        """
        )
        ctrl.addWidget(self.cmb_sample)

        # 分箱宽度
        ctrl.addWidget(QLabel('分箱宽度:'))
        self.spin_bin = QDoubleSpinBox(self)
        self.spin_bin.setRange(0.1, 1e6)
        self.spin_bin.setDecimals(1)
        self.spin_bin.setValue(1.0)
        ctrl.addWidget(self.spin_bin)

        # 应用按钮
        self.btn_apply = QPushButton()
        self.btn_apply.setIcon(get_icon("change"))
        self.btn_apply.setStyleSheet(get_button_style_sheet())
        self.btn_apply.setToolTip('刷新数据')
        self.btn_apply.clicked.connect(self.update_histogram_async)
        ctrl.addWidget(self.btn_apply)
        ctrl.addStretch()

        # 添加ai按钮，引入机器学习算法自动划分断点
        self.ai_partition = QPushButton("推荐")
        self.ai_partition.setIcon(get_icon("AI"))
        self.ai_partition.setStyleSheet(get_button_style_sheet())
        self.ai_partition.setToolTip('AI智能划分')
        self.ai_partition.clicked.connect(self._on_ai_clicked)
        ctrl.addWidget(self.ai_partition)
        # 划分开关按钮
        self.btn_partition = QPushButton("划分")
        self.btn_partition.setIcon(get_icon("钢笔"))
        self.btn_partition.setStyleSheet(get_button_style_sheet())
        self.btn_partition.setToolTip('开始划分')
        self.btn_partition.setCheckable(True)
        self.btn_partition.toggled.connect(self._on_partition_toggled)
        ctrl.addWidget(self.btn_partition)

        # 清空断点
        self.btn_clear = QPushButton("清空")
        self.btn_clear.setIcon(get_icon("删除"))
        self.btn_clear.setStyleSheet(get_button_style_sheet())
        self.btn_clear.setToolTip('清空划分')
        self.btn_clear.clicked.connect(self._clear_all_lines)
        ctrl.addWidget(self.btn_clear)

        # 确认
        self.btn_confirm = QPushButton("保存")
        self.btn_confirm.setIcon(get_icon("save"))
        self.btn_confirm.setStyleSheet(get_button_style_sheet())
        self.btn_confirm.setToolTip('确认划分')
        self.btn_confirm.clicked.connect(self.accept)
        ctrl.addWidget(self.btn_confirm)

        layout.addLayout(ctrl)

        # PlotWidget
        self.plot = HistogramPlotWidget(self)

        layout.addWidget(self.plot)

    def _init_time_range(self):
        now = QDateTime.currentDateTime()
        self.end_dt.setDateTime(now)
        self.start_dt.setDateTime(now.addDays(-12))

    def _restore_breakpoints(self, text: str):
        """根据保存的文本恢复断点"""
        for line in text.splitlines():
            parts = [item.strip() for item in line.split(' ~ ')]
            if len(parts) == 2:
                try:
                    if re.match(r'^[+-]?(?:\d+\.\d*|\.\d+|\d+)$', parts[0]):
                        start = float(parts[0])
                        self._add_cut_line(start, initial=True)
                except ValueError:
                    continue
        if re.match(r'^[+-]?(?:\d+\.\d*|\.\d+|\d+)$', parts[1]):
            self._add_cut_line(float(parts[1]), initial=True)

    def _on_partition_toggled(self, checked: bool):
        # 划分模式切换样式
        self.btn_partition.setStyleSheet(
            get_button_style_sheet().replace("background-color: #e9ecef;", "background-color:#d0f0c0;")
            if checked else get_button_style_sheet())
        self.partitioning = checked

        # 动态连接/断开 点击添加断点
        if checked:
            self.plot.scene().sigMouseClicked.connect(self._on_click)
        else:
            try:
                self.plot.scene().sigMouseClicked.disconnect(self._on_click)
            except TypeError:
                pass

    def _on_ai_clicked(self):
        if self.current_data is None or len(self.current_data) == 0:
            QToolTip.showText(self.ai_partition.mapToGlobal(QPoint(0, 0)), "请先刷新并载入数据")
            return

        self.ai_partition.setEnabled(False)

        # Worker 异步计算 AI 断点
        worker = Worker(self._compute_ai_breaks, self.current_data.copy(), self.type)
        worker.signals.finished.connect(self._on_ai_finished)
        worker.signals.error.connect(self._reset_ai_btn)
        self.thread_pool.start(worker)

    def _compute_ai_breaks(self, data: np.ndarray, type_: str):
        if type_ == "partition":
            jenks_tool = JenksBreakpoint()
            # 忽略首尾
            return jenks_tool.call(data)
        else:
            def robust_range(data, n_components=3, std_scale=3):
                data = np.asarray(data).reshape(-1, 1)

                # 判断是否为离散变量（唯一值较少）
                unique_values = np.unique(data)
                if len(unique_values) <= 10:
                    return [float(data.min()), float(data.max())]

                # 拟合 GMM 模型
                gmm = GaussianMixture(n_components=n_components, random_state=0)
                gmm.fit(data)

                # 获取每个分布的均值和标准差
                means = gmm.means_.flatten()
                stds = np.sqrt(gmm.covariances_).flatten()

                # 找到最左和最右峰的均值及其 std
                lower = min(means[id] - std_scale * stds[id] for id in range(len(means)))
                upper = max(means[id] + std_scale * stds[id] for id in range(len(means)))

                trimmed = data[(data >= lower) & (data <= upper)]
                if trimmed.size == 0:
                    trimmed = data

                return [float(trimmed.min()), float(trimmed.max())]

            return robust_range(data)

    def _on_ai_finished(self, breaks):
        self._reset_ai_btn()
        self._clear_all_lines()
        for x in breaks:
            self._add_cut_line(float(x))
            self.plot.addItem(self.cut_lines[-1])

    def _reset_ai_btn(self, *args):
        # *args absorbs possible error tuple
        self.ai_partition.setEnabled(True)

    def update_histogram_async(self):
        self.btn_apply.setEnabled(False)
        self.btn_apply.setIcon(get_icon("沙漏"))
        start = self.start_dt.dateTime().toPyDateTime()
        end = self.end_dt.dateTime().toPyDateTime()
        sample = self.cmb_sample.currentData()
        worker = Worker(self.dfs, self.point_name, start, end, sample, policy="update")
        worker.signals.finished.connect(self._on_data_fetched)
        worker.signals.error.connect(self._reset_apply_btn)
        self.thread_pool.start(worker)

    def _reset_apply_btn(self):
        self.btn_apply.setEnabled(True)
        self.btn_apply.setIcon(get_icon("change"))

    def _on_data_fetched(self, data):
        if self.bar_item:
            self.plot.removeItem(self.bar_item)

        ts, ys = data.get(self.point_name, (None, None))
        if ys is None or len(ys) == 0:
            self.current_data = None
            self._reset_apply_btn()
            return

        arr = np.asarray(ys)
        self.current_data = arr

        w = self.spin_bin.value()
        mn, mx = arr.min(), arr.max()
        if mn == mx:
            mn, mx = mn - 0.1, mx + 0.1
        bins = np.arange(mn, mx + w, w)
        y, x = np.histogram(arr, bins=bins)
        self.bar_item = pg.BarGraphItem(x=x[:-1], height=y, width=w, brush="blue")
        self.plot.addItem(self.bar_item)

        self._reset_apply_btn()

    def _add_cut_line(self, x: float, initial=False):
        ln = DraggableLine(x)
        ln.setZValue(10)  # 设置较高的Z值
        self.cut_lines.append(ln)
        if initial:
            try:
                self.plot.addItem(ln)
            except:
                pass

    def _on_click(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        vb = self.plot.getViewBox()
        pos = ev.scenePos()
        if not vb.sceneBoundingRect().contains(pos):
            return

        x = vb.mapSceneToView(pos).x()
        tol = self.spin_bin.value() * 0.1

        # 检查是否有现有断点附近的点击
        for ln in self.cut_lines:
            if abs(ln.value() - x) < tol:
                return

        self._add_cut_line(x)
        self.plot.addItem(self.cut_lines[-1])

    def _delete_line(self, line):
        if line in self.cut_lines:
            self.plot.removeItem(line)
            self.cut_lines.remove(line)

    def _clear_all_lines(self):
        for ln in list(self.cut_lines):
            self._delete_line(ln)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Delete:
            for ln in list(self.cut_lines):
                if ln.isUnderMouse():
                    self._delete_line(ln)
        super().keyPressEvent(ev)

    def get_intervals(self):
        if self.type == "partition":
            xs = sorted(ln.value() for ln in self.cut_lines)
            return [(xs[i], xs[i + 1]) for i in range(len(xs) - 1)]
        else:
            xs = sorted(ln.value() for ln in self.cut_lines)
            return [xs[0], xs[-1]]

    def accept(self):
        # 离开划分模式
        if self.btn_partition.isChecked():
            self.btn_partition.setChecked(False)
        super().accept()
