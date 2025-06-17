import pyqtgraph as pg
from datetime import datetime
from PyQt5.QtCore import Qt, QDateTime, QThreadPool
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QListWidget,
    QDateTimeEdit,
    QPushButton,
    QLabel,
    QListWidgetItem,
    QScrollArea,
    QDialog,
    QAbstractItemView,
    QCheckBox,
    QSpacerItem,
    QSizePolicy,
    QComboBox,
    QMessageBox,
)
from application.dialogs.time_selector_dialog import TimeSelectorDialog
from application.utils.threading_utils import Worker
from application.utils.utils import styled_dt, get_icon, get_button_style_sheet
from application.widgets.selectable_region import SelectableRegionItem
from application.widgets.trend_plot_widget import TrendPlotWidget


class TimeRangeDialog(QDialog):
    def __init__(self, data_fetcher, current_text=None, parent=None):
        super().__init__(parent)
        self.df = data_fetcher
        self.parent = parent
        self.default_ranges = self.load(current_text) or []
        self.setWindowTitle("⏱️ 时间范围选择器")
        self.resize(1500, 800)
        self.tags = parent.gather_tags() if parent else {}
        self._updating = False
        self.selected_ranges = []  # [(t0,t1),...]
        self.region_items = []  # [SelectableRegionItem,...]
        self.thread_pool = QThreadPool.globalInstance()

        self._build_ui()
        self._init_time()
        self._load_tags()
        self.chk_all.setCheckState(Qt.Checked)
        self._apply_chk_all()
        self._apply_default_region()
        self.update_plot_async()

    def load(self, current_text: str):
        return (
            [
                [
                    datetime.strptime(item.strip(), "%Y-%m-%d %H:%M:%S")
                    for item in time_range.split("~")
                ]
                for time_range in current_text.split("\n")
            ]
            if len(current_text) > 0
            else None
        )

    def _build_ui(self):
        splitter = QSplitter(Qt.Horizontal, self)
        left = QWidget()
        lv = QVBoxLayout(left)
        left.setMaximumWidth(700)
        self.chk_all = QCheckBox("全选/全不选", self)
        self.chk_all.stateChanged.connect(self._apply_chk_all)
        self.point_list = QListWidget(self)
        self.point_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.point_list.itemChanged.connect(self._sync_chk_all)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.point_list)
        lv.addWidget(self.chk_all)
        lv.addWidget(scroll)

        right = QWidget()
        rv = QVBoxLayout(right)
        ctrl = QHBoxLayout()
        self.start_time = styled_dt(QDateTimeEdit())
        self.end_time = styled_dt(QDateTimeEdit())
        self.cmb_sample = QComboBox(self)
        for v in ["600", "2000", "5000"]:
            self.cmb_sample.addItem(v, int(v))
        self.btn_apply = QPushButton()
        self.btn_apply.setIcon(get_icon("change"))
        self.btn_apply.setToolTip("更新图表")
        self.btn_apply.setStyleSheet(get_button_style_sheet())
        self.btn_apply.clicked.connect(self.update_plot_async)
        ctrl.addWidget(QLabel("开始:"))
        ctrl.addWidget(self.start_time)
        ctrl.addWidget(QLabel("结束:"))
        ctrl.addWidget(self.end_time)
        ctrl.addWidget(QLabel("采样数:"))
        ctrl.addWidget(self.cmb_sample)
        ctrl.addWidget(self.btn_apply)
        ctrl.addSpacerItem(
            QSpacerItem(20, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        # 添加、删除、确认按钮
        manual = QPushButton()
        manual.setIcon(get_icon("手动设置"))
        manual.setToolTip("手动选择时间范围")
        manual.clicked.connect(self._manual_region)
        manual.setStyleSheet(get_button_style_sheet())
        self.btn_sel = QPushButton()
        self.btn_sel.setIcon(get_icon("框选"))
        self.btn_sel.setToolTip("框选时间范围")
        self.btn_sel.setCheckable(True)
        self.btn_sel.setStyleSheet(get_button_style_sheet())
        self.btn_sel.clicked.connect(self._toggled)
        btn_add = QPushButton()
        btn_add.setIcon(get_icon("勾号"))
        btn_add.setToolTip("添加当前时间范围")
        btn_add.setStyleSheet(get_button_style_sheet())
        btn_add.clicked.connect(self._add_current_region)
        btn_delete = QPushButton()
        btn_delete.setIcon(get_icon("删除"))
        btn_delete.setToolTip("删除当前时间范围")
        btn_delete.setStyleSheet(get_button_style_sheet())
        btn_delete.clicked.connect(self._delete_selected_region)
        btn_confirm = QPushButton()
        btn_confirm.setIcon(get_icon("save"))
        btn_confirm.setToolTip("保存时间范围")
        btn_confirm.setStyleSheet(get_button_style_sheet())
        btn_confirm.clicked.connect(self.accept)
        ctrl.addWidget(manual)
        ctrl.addWidget(self.btn_sel)
        ctrl.addWidget(btn_add)
        ctrl.addWidget(btn_delete)
        ctrl.addWidget(btn_confirm)

        rv.addLayout(ctrl)
        self.plot = TrendPlotWidget(parent=self.parent)
        rv.addWidget(self.plot)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([200, 1100])
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(splitter)

    def _toggled(self, checked: bool):
        # 划分模式切换样式
        self.btn_sel.setStyleSheet(
            get_button_style_sheet().replace("background-color: #e9ecef;", "background-color:#d0f0c0;")
            if checked else get_button_style_sheet())
        if checked:
            self.plot.enable_selection()
        else:
            self.plot.disable_selection()

    def _init_time(self):
        now = QDateTime.currentDateTime()
        self.end_time.setDateTime(now)
        self.start_time.setDateTime(now.addSecs(-12 * 3600))

    def _load_tags(self):
        self.point_list.clear()
        for t in self.tags:
            it = QListWidgetItem(t)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            self.point_list.addItem(it)

    def _apply_chk_all(self):
        if self._updating:
            return
        st = self.chk_all.checkState()
        self._updating = True
        for i in range(self.point_list.count()):
            self.point_list.item(i).setCheckState(st)
        self._updating = False

    def _sync_chk_all(self, _):
        if self._updating:
            return
        tot = self.point_list.count()
        chk = sum(
            1 for i in range(tot) if self.point_list.item(i).checkState() == Qt.Checked
        )
        self._updating = True
        if chk == 0:
            self.chk_all.setCheckState(Qt.Unchecked)
        elif chk == tot:
            self.chk_all.setCheckState(Qt.Checked)
        else:
            self.chk_all.setCheckState(Qt.PartiallyChecked)
        self._updating = False

    def _apply_default_region(self):
        # 清除旧数据
        self.selected_ranges.clear()
        self.region_items.clear()
        # 设置起止时间显示整体范围
        if self.default_ranges:
            start = min(t0 for t0, _ in self.default_ranges)
            end = max(t1 for _, t1 in self.default_ranges)
            self.start_time.setDateTime(start)
            self.end_time.setDateTime(end)
        else:
            self._init_time()
        # 渲染每段区域，可拖拽
        for idx, (t0, t1) in enumerate(self.default_ranges):
            # 维护 selected_ranges
            self.selected_ranges.append((t0, t1))
            item = SelectableRegionItem(
                index=idx,
                callback=self._update_range,
                values=[t0.timestamp(), t1.timestamp()],
                brush=(255, 0, 0, 80),
                pen=pg.mkPen((200, 0, 0), width=2),
            )
            self.plot.addItem(item)
            self.region_items.append(item)

    def _update_range(self, idx, new_range):
        # callback 更新 selected_ranges
        self.selected_ranges[idx] = new_range

    def update_plot_async(self):
        # 首先禁用应用按钮，防止重复点击
        self.btn_apply.setEnabled(False)
        self.btn_apply.setIcon(get_icon("沙漏"))
        pts = [
            self.point_list.item(i).text()
            for i in range(self.point_list.count())
            if self.point_list.item(i).checkState() == Qt.Checked
        ]
        sample = self.cmb_sample.currentData()
        start = self.start_time.dateTime().toPyDateTime()
        end = self.end_time.dateTime().toPyDateTime()

        # 更新时间范围显示
        if hasattr(self.parent, "range_combo") and self.parent.range_combo:
            # 将索引重置为自定义
            self.parent.range_combo.setCurrentIndex(0)

        worker = Worker(
            self.df.call_batch, [pt.split("\n")[0] for pt in pts], start, end, sample
        )
        worker.signals.finished.connect(self._on_data_fetched_segment)
        QApplication.processEvents()
        self.thread_pool.start(worker)

    def _on_data_fetched_segment(self, data):
        self.plot.clear_all()
        self.plot.plot_multiple(data)
        # 设置 X 轴
        r0 = self.start_time.dateTime().toPyDateTime().timestamp()
        r1 = self.end_time.dateTime().toPyDateTime().timestamp()
        self.plot.setXRange(r0, r1, padding=0)
        self.btn_apply.setEnabled(True)
        self.btn_apply.setIcon(get_icon("change"))

    def _clear_region(self):
        self.plot.disable_selection()

    def _add_current_region(self):
        if self.plot._is_selecting:
            r = self.plot.region.getRegion()
            if abs(r[1] - r[0]) < 1e-3:
                QMessageBox.warning(self, "提示", "选区范围无效")
                return
            t0, t1 = datetime.fromtimestamp(r[0]), datetime.fromtimestamp(r[1])
            idx = len(self.selected_ranges)
            self.selected_ranges.append((t0, t1))
            item = SelectableRegionItem(
                index=idx,
                callback=self._update_range,
                values=[r[0], r[1]],
                brush=(255, 0, 0, 80),
                pen=pg.mkPen((200, 0, 0), width=2),
            )
            self.plot.addItem(item)
            self.region_items.append(item)
            self._clear_region()
            self.btn_sel.setChecked(False)
            self.btn_sel.setStyleSheet(get_button_style_sheet())

    def _delete_selected_region(self):
        to_remove = [i for i, reg in enumerate(self.region_items) if reg.selected]
        for i in sorted(to_remove, reverse=True):
            self.plot.removeItem(self.region_items[i])
            del self.region_items[i]
            del self.selected_ranges[i]

    def accept(self):
        if self.plot._is_selecting:
            self.plot.disable_selection()
        super().accept()

    def get_selected_time_ranges(self):
        time_ranges = [
            (t0.strftime("%Y-%m-%d %H:%M:%S"), t1.strftime("%Y-%m-%d %H:%M:%S"))
            for t0, t1 in self.selected_ranges
        ]
        return (
            "\n".join(["~".join(range) for range in time_ranges])
            if len(time_ranges) > 0
            else ""
        )

    @staticmethod
    def save(key, val):
        if "~" in val:
            val = [
                [item.strip() for item in range.split("~")] for range in val.split("\n")
            ]
            return key, val
        return key, []

    def _manual_region(self, ev):
        start_time = (
            self.start_time.dateTime().toPyDateTime().strftime("%Y-%m-%d %H:%M:%S")
        )
        end_time = self.end_time.dateTime().toPyDateTime().strftime("%Y-%m-%d %H:%M:%S")
        # 弹出开始
        dlg = TimeSelectorDialog(current_value=start_time, title="选择起始时间")
        if dlg.exec_() != QDialog.Accepted:
            return
        t0_str = dlg.get_time()
        t0 = datetime.strptime(t0_str, "%Y-%m-%d %H:%M:%S")
        # 弹出结束
        dlg2 = TimeSelectorDialog(current_value=end_time, title="选择结束时间")
        if dlg2.exec_() != QDialog.Accepted:
            return
        t1_str = dlg2.get_time()
        t1 = datetime.strptime(t1_str, "%Y-%m-%d %H:%M:%S")
        # 应用区域
        start_ts, end_ts = t0.timestamp(), t1.timestamp()
        if end_ts <= start_ts:
            QMessageBox.warning(self, "错误", "结束时间必须大于开始时间")
            return
        self.plot._is_selecting = True
        self.plot.region.setRegion([start_ts, end_ts])
        self.plot.region.show()
        self._add_current_region()


if __name__ == "__main__":
    pass
