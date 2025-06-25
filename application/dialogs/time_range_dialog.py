import ctypes
import re
from collections import defaultdict

import pyqtgraph as pg
from datetime import datetime
from PyQt5.QtCore import Qt, QDateTime, QThreadPool, QSize, QPropertyAnimation, QEvent, QPoint
from PyQt5.QtGui import QColor, QFont
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
    QMessageBox, QMenu,
)
from application.dialogs.time_selector_dialog import TimeSelectorDialog
from application.tools.jenks_breakpoint import JenksBreakpoint
from application.tools.train_data_select import TrainDataSelect
from application.utils.data_format_transform import list2str
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
        # 添加窗口标志
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        self.resize(1500, 800)
        self.tags =  parent.gather_tags(with_type=True) if parent else []
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
        left.setMaximumWidth(1000)
        self.chk_all = QCheckBox("全选/全不选", self)
        self.chk_all.stateChanged.connect(self._apply_chk_all)
        self.point_list = QListWidget(self)
        self.point_list.itemChanged.connect(self._sync_chk_all)
        # 在 _build_ui 中添加事件过滤器
        self.point_list.viewport().installEventFilter(self)
        self.point_list.setStyleSheet(
            """
                    QListWidget {
                        border: 1px solid #e0e0e0;
                        border-radius: 4px;
                        outline: 0px;
                    }
                    QListWidget::item {
                        padding: 6px 12px;
                        margin: 1px 0;
                        border-radius: 3px;
                        color: #202020;
                    }
                    QListWidget::item:hover {
                        background-color: #f5f5f5;
                    }
                    QListWidget::item:selected {
                        background-color: #e6f7ff;
                        color: #000000;
                    }
                    QListWidget::item:checked {
                        color: #1890ff;
                        font-weight: bold;
                    }
                    QCheckBox {
                        color: #495057;
                        font-size: 11px;
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
        
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                        height: 0px;
                    }
        
                    QScrollBar:horizontal {
                        border: none;
                        background: #f8f9fa;
                        height: 10px;
                        margin: 0px;
                    }
        
                    QScrollBar::handle:horizontal {
                        background: #adb5bd;
                        border-radius: 5px;
                        min-width: 30px;
                    }
        
                    QScrollBar::handle:horizontal:hover {
                        background: #868e96;
                    }
        
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                        width: 0px;
                    }
                """
        )

        self._init_signals()
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
        self.btn_suggest = QPushButton("推荐")
        self.btn_suggest.setIcon(get_icon("AI"))
        self.btn_suggest.setToolTip("根据稳定性自动推荐训练窗口")
        self.btn_suggest.setStyleSheet(get_button_style_sheet())
        self.btn_suggest.clicked.connect(self._suggest_windows_async)
        ctrl.addWidget(self.btn_suggest)

        manual = QPushButton("输入")
        manual.setIcon(get_icon("手动设置"))
        manual.setToolTip("手动选择时间范围")
        manual.clicked.connect(self._manual_region)
        manual.setStyleSheet(get_button_style_sheet())
        self.btn_sel = QPushButton("框选")
        self.btn_sel.setIcon(get_icon("框选"))
        self.btn_sel.setToolTip("框选时间范围")
        self.btn_sel.setCheckable(True)
        self.btn_sel.setStyleSheet(get_button_style_sheet())
        self.btn_sel.clicked.connect(self._toggled)
        btn_add = QPushButton("确认")
        btn_add.setIcon(get_icon("勾号"))
        btn_add.setToolTip("添加当前时间范围")
        btn_add.setStyleSheet(get_button_style_sheet())
        btn_add.clicked.connect(self._add_current_region)
        btn_delete = QPushButton("删除")
        btn_delete.setIcon(get_icon("删除"))
        btn_delete.setToolTip("删除当前时间范围")
        btn_delete.setStyleSheet(get_button_style_sheet())
        btn_delete.clicked.connect(self._delete_selected_region)
        btn_confirm = QPushButton("保存")
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
        self.plot = TrendPlotWidget(parent=self.parent, show_service=False)
        rv.addWidget(self.plot)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([350, 1100])
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(splitter)

    def _suggest_windows_async(self):
        if self.current_data is None:
            QMessageBox.information(self, "提示", "请先点“更新图表”载入数据")
            return
        self.btn_suggest.setEnabled(False)
        train_dataset_suggest_tool = TrainDataSelect()
        worker = Worker(
            train_dataset_suggest_tool.call,
            self.current_data,  # 在 _on_data_fetched_segment 里把 data 暂存到 self.current_data
        )
        worker.signals.finished.connect(self._on_suggest_ready)
        worker.signals.error.connect(lambda *_: self._reset_suggest_btn())
        self.thread_pool.start(worker)

    def _on_suggest_ready(self, win_list):
        self._reset_suggest_btn()
        if not win_list:
            QMessageBox.information(self, "提示", "未检测到高信息量区域")
            return

        # 清掉旧推荐高亮
        if hasattr(self, "_suggest_regions"):
            for reg in self._suggest_regions:
                self.plot.removeItem(reg)
        self._suggest_regions = []

        for i, (t0, t1) in enumerate(win_list, 1):
            # 绿色半透明高亮
            item = SelectableRegionItem(
                index=i,
                callback=self._update_range,
                values=[t0, t1],
                brush=(255, 0, 0, 80),
                pen=pg.mkPen((200, 0, 0), width=2),
            )
            self.plot.addItem(item)
            self.region_items.append(item)
            self._suggest_regions.append(item)
            self.selected_ranges.append((datetime.fromtimestamp(t0), datetime.fromtimestamp(t1)))

    def _apply_suggestion(self, win):
        t0, t1 = map(datetime.fromtimestamp, win)
        self.start_time.setDateTime(t0)
        self.end_time.setDateTime(t1)
        # 自动更新 plot 方便预览
        self.update_plot_async()

    def _reset_suggest_btn(self):
        self.btn_suggest.setEnabled(True)

    def _init_signals(self):
        """初始化信号连接"""
        self.point_list.itemClicked.connect(self._handle_item_click)
        self.point_list.itemDoubleClicked.connect(self._handle_item_double_click)
        self.point_list.itemChanged.connect(self._handle_item_change)

    def _handle_item_click(self, item):
        if item.data(Qt.UserRole) == "group":
            group = item.text()[2:]
            self._toggle_group_selection(item, group)
            return

    def _handle_item_double_click(self, item):
        if item.data(Qt.UserRole) == "group":
            group = item.text()[2:]
            self._toggle_group_expansion(item, group)
            return
        elif item.data(Qt.UserRole):
            item.setCheckState(
                Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
            )
            self._update_group_header_state(item.data(Qt.UserRole))

    def _handle_item_change(self, item):
        item_type = item.data(Qt.UserRole)
        if item_type and item_type in self.group_items:
            self._update_group_header_state(item_type)

    def eventFilter(self, source, event):
        if (
            source == self.point_list.viewport()
            and event.type() == QEvent.MouseButtonPress
        ):
            index = self.point_list.indexAt(event.pos())
            if index.isValid():
                item = self.point_list.item(index.row())
                if item.data(Qt.UserRole) != "group":
                    item.setCheckState(
                        Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
                    )
                    return True
        return super().eventFilter(source, event)

    def _apply_chk_all(self):
        if self._updating:
            return
        st = self.chk_all.checkState()
        self._updating = True

        for i in range(self.point_list.count()):
            item = self.point_list.item(i)
            if item.data(Qt.UserRole) not in ["group", None]:
                item.setCheckState(st)

        for group in self.group_items.values():
            self._update_group_header_state(group.text()[2:])

        self._updating = False

    def _toggle_group_expansion(self, item, group):
        row = self.point_list.row(item)
        is_expanding = False
        for i in range(row + 1, self.point_list.count()):
            child = self.point_list.item(i)
            if child.data(Qt.UserRole) == "group":
                break
            is_expanding = child.isHidden()
            break

        for i in range(row + 1, self.point_list.count()):
            child = self.point_list.item(i)
            if child.data(Qt.UserRole) == "group":
                break
            child.setHidden(not is_expanding)

        # 更新符号
        if is_expanding:
            item.setText(f"▼ {group}")
        else:
            item.setText(f"▶ {group}")

    def _toggle_group_selection(self, item, group):
        row = self.point_list.row(item)
        is_checked = item.checkState() == Qt.Checked

        for i in range(row + 1, self.point_list.count()):
            child = self.point_list.item(i)
            if child.data(Qt.UserRole) == "group":
                break
            child.setCheckState(Qt.Checked if is_checked else Qt.Unchecked)

    def _load_tags(self):
        groups = defaultdict(list)
        for t in self.tags:
            type_name, name = t.split(":", 1) if ":" in t else ("其他", t)
            name = name.split("\n")[1] if "\n" in name else name
            groups[type_name].append(name)

        self.point_list.clear()
        self.group_items = {}

        for group in sorted(groups):
            header = QListWidgetItem(f"▼ {group}")
            header.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            header.setCheckState(Qt.Unchecked)
            header.setData(Qt.UserRole, "group")
            header.setFont(QFont("Segoe UI", 10, QFont.Bold))
            header.setBackground(QColor("#f0f2f5"))
            self.point_list.addItem(header)
            self.group_items[group] = header

            for name in groups[group]:
                it = QListWidgetItem(f"　{name}")
                it.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                it.setCheckState(Qt.Unchecked)
                it.setData(Qt.UserRole, group)
                self.point_list.addItem(it)

    def _update_group_header_state(self, group):
        """更新分组标题选中状态"""
        header = self.group_items[group]
        checked_count = 0
        total_count = 0

        row = self.point_list.row(header)
        for i in range(row + 1, self.point_list.count()):
            child = self.point_list.item(i)
            if child.data(Qt.UserRole) == "group":  # 遇到下一个分组停止
                break
            total_count += 1
            if child.checkState() == Qt.Checked:
                checked_count += 1

        # 更新分组标题状态
        if checked_count == 0:
            header.setCheckState(Qt.Unchecked)
        elif checked_count == total_count:
            header.setCheckState(Qt.Checked)
        else:
            header.setCheckState(Qt.PartiallyChecked)

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

    def _toggle_group(self, item):
        # 判断是否是分组标题
        group_text = item.text()[2:] if item.text().startswith("▶ ") else None
        if group_text in self.group_items:
            is_checked = item.checkState() == Qt.Checked
            # 同步组内项
            for i in range(self.point_list.count()):
                it = self.point_list.item(i)
                if it.data(Qt.UserRole) == group_text:
                    it.setCheckState(Qt.Checked if is_checked else Qt.Unchecked)

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

        # 修正测点名称提取逻辑
        pts = []
        for i in range(self.point_list.count()):
            item = self.point_list.item(i)
            if (
                item.data(Qt.UserRole) != "group" and
                item.flags() & Qt.ItemIsUserCheckable
                and item.checkState() == Qt.Checked
            ):
                # 提取原始测点名（去除缩进空格）
                raw_name = item.text().strip()
                pts.append(raw_name)

        sample = self.cmb_sample.currentData()
        start = self.start_time.dateTime().toPyDateTime()
        end = self.end_time.dateTime().toPyDateTime()

        # 更新时间范围显示
        if hasattr(self.parent, "range_combo") and self.parent.range_combo:
            self.parent.range_combo.setCurrentIndex(0)

        worker = Worker(
            self.df.call_batch,
            [pt.split("|")[0].strip() for pt in pts],  # 确保原始数据标识符正确
            start,
            end,
            sample,
        )
        worker.signals.finished.connect(self._on_data_fetched_segment)
        worker.signals.error.connect(
            lambda err: (
                self.btn_apply.setEnabled(True),
                self.btn_apply.setIcon(get_icon("change"))
            )
        )
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
        self.current_data = data  # <—— 加这一行

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
        # 将时间序列进行排列
        self.selected_ranges = sorted(self.selected_ranges, key=lambda x: x[0])
        # 将有交集的时间集合合并
        self.merged_selected_ranges = []
        for t0, t1 in self.selected_ranges:
            if self.merged_selected_ranges and self.merged_selected_ranges[-1][1] >= t0:
                self.merged_selected_ranges[-1][1] = t1
            else:
                self.merged_selected_ranges.append([t0, t1])
        time_ranges = [
            (t0.strftime("%Y-%m-%d %H:%M:%S"), t1.strftime("%Y-%m-%d %H:%M:%S"))
            for t0, t1 in self.merged_selected_ranges
        ]
        return (
            list2str(time_ranges)
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

    def nativeEvent(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(message.__int__())
            if msg.message == 0x00A3:
                if self.isMaximized():
                    self.showNormal()
                else:
                    self.showMaximized()
                return True, 0
        return super().nativeEvent(eventType, message)


if __name__ == "__main__":
    pass
