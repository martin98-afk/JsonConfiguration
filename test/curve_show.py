import sys

import httpx
import numpy as np
import pyqtgraph as pg
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QListWidget, QDateTimeEdit, QPushButton,
                             QLabel, QListWidgetItem, QScrollArea)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal
from PyQt5.QtGui import QColor

class TimeRangeSelector(pg.PlotWidget):
    range_selected = pyqtSignal(datetime, datetime)
    selection_started = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setBackground('w')
        self.setMouseEnabled(y=False)
        self.curves = []
        self._is_selecting = False  # 控制框选状态
        self._start_pos = None  # 初始化_start_pos
        # 初始化时间轴
        self.axis = pg.DateAxisItem(orientation='bottom')
        self.setAxisItems({'bottom': self.axis})

        # 选择区域
        self.region = pg.LinearRegionItem(brush=(0, 200, 0, 50), pen=QColor(0, 200, 0))
        self.region.setZValue(1000)
        self.region.hide()
        self.addItem(self.region)

        # 交叉线
        self.crosshair = pg.InfiniteLine(angle=90, pen=pg.mkPen('#999', width=1, style=Qt.DashLine))
        self.addItem(self.crosshair)
        self.crosshair.hide()

        # 事件绑定
        self.scene().sigMouseMoved.connect(self.mouse_moved)
        self.region.sigRegionChanged.connect(self.region_changed)

        self.dragging = False

    def mouse_moved(self, pos):
        """处理鼠标移动事件"""
        mouse_point = self.plotItem.vb.mapSceneToView(pos)
        self.crosshair.setPos(mouse_point.x())

        if self.viewRect().contains(mouse_point):
            self.crosshair.show()
            self.show_tooltip(mouse_point)
        else:
            self.crosshair.hide()

    def show_tooltip(self, pos):
        """显示工具提示"""
        try:
            timestamp = pos.x()
            if timestamp < 0 or timestamp > 2 ** 31 - 1:
                self.setToolTip("")
                return
            x_time = datetime.fromtimestamp(timestamp)
            tooltip = [x_time.strftime('%Y-%m-%d %H:%M:%S')]
            for curve in self.curves:
                x_data, y_data = curve.getData()
                if x_data is None or len(x_data) == 0:
                    continue
                idx = np.abs(x_data - timestamp).argmin()
                if abs(x_data[idx] - timestamp) < 60:  # 1分钟误差范围
                    tooltip.append(f"{curve.name()}: {y_data[idx]:.2f}")
            self.setToolTip("\n".join(tooltip))
        except (OSError, ValueError) as e:
            self.setToolTip("")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            view_pos = self.plotItem.vb.mapSceneToView(event.pos())
            x = view_pos.x()

            if self._is_selecting:  # 判断是否启用框选
                if not self._start_pos:
                    # 第一次点击：开始框选
                    self._start_pos = x
                    self.region.setRegion([x, x])
                    self.region.show()
                    self.selection_started.emit()
                else:
                    # 第二次点击：结束框选
                    self._start_pos = None
                    start, _ = self.region.getRegion()
                    self.region.setRegion([start, x])  # 固定终点，保留框选
                    # 发射信号给上层
                    from datetime import datetime
                    t0 = datetime.fromtimestamp(min(start, x))
                    t1 = datetime.fromtimestamp(max(start, x))
                    self.range_selected.emit(t0, t1)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_selecting and self._start_pos is not None:
            current_pos = self.plotItem.vb.mapSceneToView(event.pos()).x()
            self.region.setRegion([self._start_pos, current_pos])
        super().mouseMoveEvent(event)

    def reset_selection(self):
        """确认或取消后调用，重置区域显示和状态。"""
        self._is_selecting = False
        self._start_pos = None
        self.region.hide()
        self.region.setRegion([0, 0])
        self.crosshair.hide()

    def region_changed(self):
        # 处理区域变化的逻辑
        pass

    def enable_selection(self):
        """启用框选功能"""
        self._is_selecting = True

    def disable_selection(self):
        """禁用框选功能"""
        self.reset_selection()


class CurveViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("实时曲线查看器")
        self.setGeometry(100, 100, 1500, 800)
        self.data_cache = {}  # 数据缓存
        self.init_ui()
        self.load_dummy_data()

    def init_ui(self):
        main_splitter = QSplitter(Qt.Horizontal)

        # 左侧控制面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # 时间选择
        time_layout = QHBoxLayout()
        self.start_time = QDateTimeEdit()
        self.end_time = QDateTimeEdit()
        self.start_time.setDateTime(QDateTime.currentDateTime().addSecs(-3600))
        self.end_time.setDateTime(QDateTime.currentDateTime())
        self.btn_apply = QPushButton("应用")

        time_layout.addWidget(QLabel("开始:"))
        time_layout.addWidget(self.start_time)
        time_layout.addWidget(QLabel("结束:"))
        time_layout.addWidget(self.end_time)
        time_layout.addWidget(self.btn_apply)

        # 框选按钮
        self.btn_select_range = QPushButton("框选时间范围")
        left_layout.addWidget(self.btn_select_range)

        # 测点列表
        self.point_list = QListWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.point_list)

        left_layout.addLayout(time_layout)
        left_layout.addWidget(QLabel("监测点:"))
        left_layout.addWidget(scroll)

        # 右侧绘图区域
        self.plot_widget = TimeRangeSelector()

        # 操作按钮
        self.btn_confirm = QPushButton("✓ 确认")
        self.btn_cancel = QPushButton("✗ 取消")
        self.btn_confirm.hide()
        self.btn_cancel.hide()

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_confirm)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.setContentsMargins(0, 0, 20, 20)

        # 右侧主布局
        right_layout = QVBoxLayout()
        right_layout.addLayout(btn_layout)
        right_layout.addWidget(self.plot_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_panel = QWidget()
        right_panel.setLayout(right_layout)

        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([300, 900])

        # 信号连接
        self.btn_apply.clicked.connect(self.update_plot)
        self.point_list.itemChanged.connect(self.update_plot)
        self.plot_widget.selection_started.connect(self.show_buttons)
        self.plot_widget.range_selected.connect(self.on_range_selected)
        self.btn_confirm.clicked.connect(self.confirm_selection)
        self.btn_cancel.clicked.connect(self.cancel_selection)
        self.btn_select_range.clicked.connect(self.toggle_select_range)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(main_splitter)

    def show_buttons(self):
        """显示操作按钮"""
        self.btn_confirm.show()
        self.btn_cancel.show()

    def fetch_data_from_api(self, tag_name, start_time, end_time):
        """从API获取数据"""
        params = {
            "span": 2,
            "dataMode": 3,
            "startTime": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "tagNames[]": tag_name
        }

        try:
            with httpx.Client(base_url="http://172.16.134.122:8900") as client:
                response = client.get(
                    url="/rest/database/sis/getSeriesValuesByNameList",
                    params=params,
                    timeout=10
                )
            if response.status_code == 200:
                data = response.json()
                if data["success"]:
                    items = data["result"]["items"]
                    if items:
                        points = items[0]["value"]
                        times = [datetime.strptime(p["timeStamp"], "%Y-%m-%d %H:%M:%S").timestamp() for p in points]
                        values = [p["value"] for p in points]
                        return np.array(times), np.array(values)
            return None, None
        except Exception as e:
            print(f"数据获取失败: {str(e)}")
            return None, None

    def load_dummy_data(self):
        """初始化测点列表（根据实际需求修改）"""
        sample_points = ["AN_LK_QT_FJ_16_34", "AN_LK_QT_FJ_19_05", "AN_LK_QT_FJ_1_25"]  # 示例测点
        for point in sample_points:
            item = QListWidgetItem(point)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.point_list.addItem(item)

    def update_plot(self):
        """更新曲线图"""
        # 清除旧曲线但保留选择区域
        for item in self.plot_widget.items():
            if isinstance(item, pg.PlotCurveItem):
                self.plot_widget.removeItem(item)
        self.plot_widget.curves = []

        selected_points = [
            self.point_list.item(i).text()
            for i in range(self.point_list.count())
            if self.point_list.item(i).checkState() == Qt.Checked
        ]

        start_dt = self.start_time.dateTime().toPyDateTime()
        end_dt = self.end_time.dateTime().toPyDateTime()

        # 绘制曲线
        colors = ['#0078d7', '#e81123', '#107c10', '#881798', '#f7630c']
        for i, tag_name in enumerate(selected_points):
            # 检查缓存
            if tag_name not in self.data_cache or \
               self.data_cache[tag_name]["start"] > start_dt or \
               self.data_cache[tag_name]["end"] < end_dt:

                times, values = self.fetch_data_from_api(tag_name, start_dt, end_dt)
                if times is not None:
                    # 缓存数据
                    self.data_cache[tag_name] = {
                        "times": times,
                        "values": values,
                        "start": start_dt,
                        "end": end_dt
                    }

            if tag_name in self.data_cache:
                cache = self.data_cache[tag_name]
                mask = (cache["times"] >= start_dt.timestamp()) & (cache["times"] <= end_dt.timestamp())

                pen = pg.mkPen(color=colors[i % 5], width=1.5)
                curve = pg.PlotCurveItem(cache["times"][mask], cache["values"][mask],
                                       pen=pen, name=tag_name)
                self.plot_widget.addItem(curve)
                self.plot_widget.curves.append(curve)

        # 保持选择区域在最上层
        self.plot_widget.region.setZValue(1000)
        self.plot_widget.autoRange()

    def confirm_selection(self):
        print(f"选择的时间范围: {self.start_sel} – {self.end_sel}")
        self.plot_widget.reset_selection()
        self.btn_confirm.hide()
        self.btn_cancel.hide()

    def cancel_selection(self):
        """取消选择"""
        self.plot_widget.reset_selection()
        self.btn_confirm.hide()
        self.btn_cancel.hide()

    def toggle_select_range(self):
        """切换框选状态"""
        if self.plot_widget._is_selecting:
            self.plot_widget.disable_selection()
            self.btn_confirm.hide()
            self.btn_cancel.hide()
        else:
            self.plot_widget.enable_selection()

    def on_range_selected(self, start_dt, end_dt):
        """收到框选完毕的时间段，再次显示确认/取消"""
        self.start_sel = start_dt
        self.end_sel = end_dt
        self.btn_confirm.show()
        self.btn_cancel.show()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    pg.setConfigOptions(antialias=True, useOpenGL=True)
    viewer = CurveViewer()
    viewer.show()
    sys.exit(app.exec_())