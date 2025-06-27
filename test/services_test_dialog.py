import datetime
from PyQt5.QtCore import Qt, QThreadPool, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView, QSplitter, QDateTimeEdit, QComboBox,
    QWidget, QLineEdit
)
import pyqtgraph as pg
from application.dialogs.services_selector_dialog import ServiceSelectorDialog
from application.tools.api_service.trenddb_fectcher import DataFetchWorker
from application.tools.api_service.servicves_test import ServiceTestFetchWorker, ServicesTest
from application.widgets.trend_plot_widget import TrendPlotWidget


# Service testing dialog
class ServiceTestDialog(QDialog):
    def __init__(self, service_fetcher, data_fetcher, parent=None):
        super().__init__(parent)
        self.service_fetcher = service_fetcher
        self.data_fetcher = data_fetcher
        self.thread_pool = QThreadPool.globalInstance()
        self.setWindowTitle("服务测试")
        self.resize(1200, 700)
        self.setFont(QFont("Microsoft YaHei", 10))

        # initial point lists
        self.working_points = parent.gather_tags(type="工况参数") if parent else []
        self.target_points = parent.gather_tags(type="控制参数") if parent else []
        self.backup_points = []
        self.selected_service = None  # (name, url)

        # state for plotting
        self.ts_list = []
        self.values_list = []
        self._service_curves = {}  # name->curve
        self.current_worker = None

        self._build_ui()
        self._refresh_working()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal)

        # left: working & backup points
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(QLabel("工况测点列表"))
        self.working_table = QTableWidget()
        self._init_table(self.working_table)
        self.working_table.cellDoubleClicked.connect(self._move_to_backup)
        lv.addWidget(self.working_table)
        lv.addWidget(QLabel("备用点列表"))
        self.backup_table = QTableWidget()
        self._init_table(self.backup_table)
        self.backup_table.cellDoubleClicked.connect(self._move_to_working)
        lv.addWidget(self.backup_table)
        self.splitter.addWidget(left)

        # right: controls & plots
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(10)
        # service selector
        svc_h = QHBoxLayout()
        svc_h.addWidget(QLabel("测试服务:"))
        self.svc_line = QLineEdit()
        self.svc_line.setReadOnly(True)
        svc_h.addWidget(self.svc_line)
        btn_srv = QPushButton("选择服务")
        btn_srv.clicked.connect(self._choose_service)
        svc_h.addWidget(btn_srv)
        rv.addLayout(svc_h)

        # control bar
        ctl = QHBoxLayout()
        self.start_dt = QDateTimeEdit(datetime.datetime.now() - datetime.timedelta(hours=12))
        self.start_dt.setCalendarPopup(True)
        self.end_dt = QDateTimeEdit(datetime.datetime.now())
        self.end_dt.setCalendarPopup(True)
        self.cmb_sample = QComboBox()
        for v in (600, 2000, 5000): self.cmb_sample.addItem(str(v), v)
        btn_apply = QPushButton("🔄 应用")
        btn_apply.clicked.connect(self._apply)
        btn_stop = QPushButton("⏹️ 停止")
        btn_stop.clicked.connect(self._stop)
        for w in (QLabel('开始:'), self.start_dt, QLabel('结束:'), self.end_dt,
                  QLabel('采样:'), self.cmb_sample, btn_apply, btn_stop): ctl.addWidget(w)
        ctl.addStretch()
        rv.addLayout(ctl)

        # plots
        self.plot_original = TrendPlotWidget()
        self.plot_test = TrendPlotWidget()
        # link X axes
        self.plot_test.plotItem.setXLink(self.plot_original.plotItem)
        rv.addWidget(self.plot_original)
        rv.addWidget(self.plot_test)

        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        main_layout.addWidget(self.splitter)

    def _init_table(self, table):
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setColumnCount(1)
        table.setHorizontalHeaderLabels(["测点名"])

    def _refresh_working(self):
        self.working_table.setRowCount(len(self.working_points))
        for i, name in enumerate(self.working_points):
            self.working_table.setItem(i, 0, QTableWidgetItem(name))
        self._refresh_backup()

    def _refresh_backup(self):
        self.backup_table.setRowCount(len(self.backup_points))
        for i, name in enumerate(self.backup_points):
            self.backup_table.setItem(i, 0, QTableWidgetItem(name))

    @pyqtSlot(int, int)
    def _move_to_backup(self, row, col):
        self.backup_points.append(self.working_points.pop(row))
        self._refresh_working()
        self._refresh_backup()

    @pyqtSlot(int, int)
    def _move_to_working(self, row, col):
        self.working_points.append(self.backup_points.pop(row))
        self._refresh_backup()
        self._refresh_working()

    def _choose_service(self):
        dlg = ServiceSelectorDialog(fetcher=self.service_fetcher, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.selected_service = dlg.get_selected_service()
            if self.selected_service:
                self.svc_line.setText(self.selected_service[0])
                # filter by service params
                params = self.service_fetcher.get_service_params(self.selected_service[-1]) or []
                keep = [pt for pt in set(self.working_points + self.backup_points) if pt in params]
                move = [pt for pt in set(self.working_points + self.backup_points) if pt not in params]
                self.working_points = keep
                self.backup_points = move
                self._refresh_working()

    def _apply(self):
        if not self.working_points or not self.selected_service:
            QMessageBox.warning(self, '提示', '请先选择测点和服务！')
            return
        start = self.start_dt.dateTime().toPyDateTime()
        end = self.end_dt.dateTime().toPyDateTime()
        sample = self.cmb_sample.currentData()
        w1 = DataFetchWorker(self.data_fetcher, self.working_points + self.target_points, start, end, sample)
        w1.signals.finished.connect(self._on_data)
        self.thread_pool.start(w1)

    def _stop(self):
        if self.current_worker:
            self.current_worker.cancel()

    @pyqtSlot(dict)
    def _on_data(self, data):
        # draw original
        self.plot_original.clear()
        self.plot_original.curves = []
        self.plot_test.clear()
        self.plot_test.curves = []
        self.ts_list = []
        self.values_list = []
        for idx, (name, (ts, ys)) in enumerate(data.items()):
            pen = pg.mkPen(color=pg.intColor(idx), width=2)
            c = pg.PlotCurveItem(ts, ys, pen=pen, name=name)
            if name in self.working_points:
                self.plot_original.addItem(c)
                self.plot_original.curves.append(c)
            elif name in self.target_points:
                self.plot_test.addItem(c)
                self.plot_test.curves.append(c)
        self.ts_list = list(ts)
        self.values_list = [list(ys) for _, (_, ys) in data.items()]
        # start service test worker
        svc_url = self.selected_service[1]
        self._service_curves = {}
        w2 = ServiceTestFetchWorker(ServicesTest(), svc_url, self.working_points, self.values_list, self.ts_list)
        self.current_worker = w2
        w2.signals.new_segment.connect(self._add_test_segment)
        w2.signals.finished.connect(self._on_test_finished)
        self.thread_pool.start(w2)

    @pyqtSlot(int, dict)
    def _add_test_segment(self, idx, segment):
        for name, y in segment.items():
            if name not in self._service_curves:
                pen = pg.mkPen(color=pg.intColor(len(self._service_curves)), width=2)
                curve = pg.PlotCurveItem([], [], pen=pen, name=name)
                self.plot_test.addItem(curve)
                self.plot_test.curves.append(curve)
                curve._segment_data = []
                self._service_curves[name] = curve
            curve = self._service_curves[name]
            # append and sort
            curve._segment_data.append((idx, self.ts_list[idx], float(y)))
            curve._segment_data.sort(key=lambda t: t[0])
            xs = [t for _, t, _ in curve._segment_data]
            ys = [v for _, _, v in curve._segment_data]
            curve.setData(xs, ys)

    @pyqtSlot()
    def _on_test_finished(self):
        QMessageBox.information(self, '完成', '所有测试段已加载完毕')

    def nativeEvent(self, eventType, message):
        return super().nativeEvent(eventType, message)
