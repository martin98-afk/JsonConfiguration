import sys
import json
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QPlainTextEdit, QTextEdit, QComboBox, QLabel, QSplitter,
    QMessageBox, QLineEdit
)
from PyQt5.QtGui import QFont, QTextCursor, QColor, QTextCharFormat

from application.tools.api_service.service_logger import ServiceLogger
from application.tools.api_service.services_search import SeviceSearcher
from application.tools.api_service.servicves_test import ServicesTest

base_url = "http://172.16.134.122:8900"
api_key = (
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiIsImtpZCI6IjAwMiJ9."
    "eyJ0ZW5hbnROYW0iOiLnp5_miLfnrqHnkIblhazlj7giLCJvcmdOYW1lIjoi5piG6ZKiIiwiaXNzIjoiU1lTIiwic2VsZWN0ZWRPcmciOiIxODU4NzgxMDEyNTUzNjI5Njk2IiwiYWRtaW5GbGciOiIxIiwib3JnSWQiOiIxODU4Nzk2NTM4OTE0OTMwNjg4IiwidXNyTmFtIjoi57O757uf566h55CG5ZGYIiwidGVuYW50Tm8iOiIxIiwid2ViU29ja2V0SXAiOiJkZWZhdWx0IiwiaWF0IjoxNzQ1MjA1OTIxLCJrYXQiOjE3NDUyMDU1NDYwODR9."
    "sayWvWVdv17F3IOl_CpiapjGvF9D_XcxHqt4KHnHh1U"
)

class JSONServiceTester(QMainWindow):
    def __init__(self, current_text: str):
        super().__init__()
        self.setWindowTitle("JSON 服务测试工具")
        self.resize(1200, 800)
        self.current_text = current_text
        self.search_results = []  # List[Tuple[int, int, int]]
        self.current_result_index = -1
        self._all_match_selections = []

        # 初始化服务组件
        self.service_searcher = SeviceSearcher(
            base_url, api_key,
            "/rest/di/service/hall?page=1&limit=1000&searchText=&orderBy=",
            "/rest/di/service/param/list?page=1&limit=10&searchText=&paramForm=0&orderBy="
        )
        self.service_tester = ServicesTest()
        self.service_logger = ServiceLogger(
            base_url, api_key,
            "/rest/di/service/detail",
            "/rest/di/service/serviceLog"
        )

        # 初始化界面
        self.init_ui()
        self.setStyleSheet(self.get_stylesheet())

        # 自动加载服务
        self.load_services()

        # 日志自动刷新定时器
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.update_service_logs)
        self.log_timer.start(1000)
        self.toggle_log_btn.setText("🛑 停止刷新")

    def init_ui(self):
        main_container = QWidget()
        self.setCentralWidget(main_container)
        main_layout = QVBoxLayout(main_container)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # —— 顶部工具栏 ——
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        toolbar.addWidget(QLabel("选择服务:"), 1)

        self.service_combo = QComboBox()
        self.service_combo.setEditable(False)
        self.service_combo.setFont(QFont("微软雅黑", 14))
        self.service_combo.setMinimumHeight(36)
        self.service_combo.currentIndexChanged.connect(self.on_service_changed)
        toolbar.addWidget(self.service_combo, 3)
        main_layout.addLayout(toolbar)

        # —— 请求/结果区域 ——
        input_result_layout = QHBoxLayout()

        input_container = QWidget()
        input_inner = QVBoxLayout(input_container)
        input_inner.setContentsMargins(0, 0, 0, 0)
        self.json_input = QPlainTextEdit()
        self.json_input.setPlaceholderText("在此输入JSON请求数据...")
        self.json_input.setPlainText(self.current_text)
        self.json_input.setFont(QFont("Consolas", 14))
        input_inner.addWidget(self.json_input)
        self.format_btn = QPushButton("✨ 美化 JSON")
        input_inner.addWidget(self.format_btn)

        result_container = QWidget()
        result_inner = QVBoxLayout(result_container)
        result_inner.setContentsMargins(0, 0, 0, 0)
        self.result_display = QPlainTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setFont(QFont("Consolas", 14))
        result_inner.addWidget(self.result_display)
        self.send_btn = QPushButton("🚀 发送请求")
        result_inner.addWidget(self.send_btn)

        input_result_layout.addWidget(input_container, 1)
        input_result_layout.addWidget(result_container, 1)

        # —— 日志区域 ——
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)

        log_toolbar = QHBoxLayout()
        log_toolbar.setSpacing(8)
        lbl = QLabel("日志过滤:")
        lbl.setFont(QFont("微软雅黑", 14))
        log_toolbar.addWidget(lbl)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("日志搜索...")
        self.search_input.setFont(QFont("Consolas", 12))
        self.search_input.setMinimumHeight(32)
        log_toolbar.addWidget(self.search_input, 4)

        self.search_up_btn = QPushButton("▲")
        self.search_down_btn = QPushButton("▼")
        for btn in (self.search_up_btn, self.search_down_btn):
            btn.setFixedSize(24, 24)
            btn.setFont(QFont("微软雅黑", 10))
            log_toolbar.addWidget(btn)

        self.search_status_label = QLabel("0/0")
        self.search_status_label.setFont(QFont("微软雅黑", 12))
        log_toolbar.addWidget(self.search_status_label)

        log_toolbar.addStretch()
        self.toggle_log_btn = QPushButton()
        self.toggle_log_btn.setFont(QFont("微软雅黑", 12))
        self.toggle_log_btn.setMinimumHeight(32)
        log_toolbar.addWidget(self.toggle_log_btn)

        log_layout.addLayout(log_toolbar)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 12))
        log_layout.addWidget(self.log_display)

        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)
        input_result_container = QWidget()
        ir_layout = QVBoxLayout(input_result_container)
        ir_layout.setContentsMargins(0, 0, 0, 0)
        ir_layout.addLayout(input_result_layout)
        splitter.addWidget(input_result_container)
        splitter.addWidget(log_container)
        splitter.setSizes([250, 550])

        # 信号绑定
        self.format_btn.clicked.connect(self.format_json)
        self.send_btn.clicked.connect(self.send_request)
        self.toggle_log_btn.clicked.connect(self.toggle_log_refresh)
        self.search_input.textChanged.connect(self.on_search_changed)
        self.search_up_btn.clicked.connect(lambda: self.navigate_search(-1))
        self.search_down_btn.clicked.connect(lambda: self.navigate_search(1))

    # 新增 on_search_changed
    def on_search_changed(self, text):
        self.apply_filter(text)

    def load_services(self):
        try:
            services = self.service_searcher.get_services_list()
            self.service_combo.clear()
            for name, path, sid in services:
                self.service_combo.addItem(name, userData=(sid, path))
            if self.service_combo.count() > 0:
                self.current_service_id = self.service_combo.itemData(0)[0]
                self.update_service_logs()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载服务失败：{str(e)}")

    def on_service_changed(self):
        if self.service_combo.count() > 0:
            self.current_service_id = self.service_combo.currentData()[0]
            self.update_service_logs()

    def send_request(self):
        if self.service_combo.count() == 0:
            return
        service_path = self.service_combo.currentData()[1]
        raw_json = self.json_input.toPlainText()
        try:
            request_data = json.loads(raw_json)
        except json.JSONDecodeError:
            QMessageBox.warning(self, "警告", "JSON格式错误")
            return
        self.worker = ServiceWorker(self.service_tester, service_path, [request_data])
        self.worker.finished.connect(self.handle_response)
        self.worker.error.connect(self.handle_error)
        self.worker.start()

    def handle_response(self, idx, result):
        try:
            formatted = json.dumps(result, indent=4, ensure_ascii=False)
            self.result_display.setPlainText(formatted)
        except:
            self.result_display.setPlainText(str(result))

    def handle_error(self, error_msg):
        QMessageBox.critical(self, "错误", error_msg)

    def update_service_logs(self):
        if self.service_combo.count() == 0:
            return
        try:
            service_id = self.service_combo.currentData()[0]
            self._raw_log_content = self.service_logger.get_service_log(service_id)
            self.apply_filter(self.search_input.text())
            self.log_display.verticalScrollBar().setValue(
                self.log_display.verticalScrollBar().maximum()
            )
        except Exception as e:
            self.log_display.setPlainText(f"日志获取失败：{str(e)}")

    def apply_filter(self, keyword):
        self._all_match_selections.clear()
        self.search_results.clear()
        if not keyword:
            self.log_display.setPlainText(self._raw_log_content)
            return

        lines = self._raw_log_content.split('\n')
        for line_no, line in enumerate(lines):
            start = 0
            while True:
                start = line.find(keyword, start)
                if start == -1:
                    break
                end = start + len(keyword)
                self.search_results.append((line_no, start, end))
                # 创建高亮选择
                block = self.log_display.document().findBlockByNumber(line_no)
                if block.isValid():
                    cursor = QTextCursor(block)
                    cursor.setPosition(block.position() + start)
                    cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor, end - start)
                    sel = QTextEdit.ExtraSelection()
                    sel.cursor = cursor
                    fmt = QTextCharFormat()
                    fmt.setBackground(QColor("#ffff00"))  # 黄色高亮
                    sel.format = fmt
                    self._all_match_selections.append(sel)
                start = end

        # 更新当前高亮
        self._current_selection = None
        self.log_display.setExtraSelections(self._all_match_selections)
        self.update_search_status()

    def highlight_all_matches(self, keyword):
        """构建所有匹配项的黄色高亮 ExtraSelection"""
        self._all_match_selections.clear()
        if not keyword:
            return
        doc = self.log_display.document()
        for line_no in self.search_results:
            block = doc.findBlockByNumber(line_no)
            text = block.text().lower()
            idx = text.find(keyword.lower())
            if idx == -1:
                continue
            cursor = QTextCursor(block)
            cursor.setPosition(block.position() + idx)
            cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor, len(keyword))
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            fmt = sel.format
            fmt.setBackground(QColor("#ffff00"))
            self._all_match_selections.append(sel)

    def navigate_search(self, direction):
        if not self.search_results:
            return

        self.current_result_index = (self.current_result_index + direction) % len(self.search_results)
        line_no, start_pos, end_pos = self.search_results[self.current_result_index]

        # 定位到匹配位置
        block = self.log_display.document().findBlockByNumber(line_no)
        if block.isValid():
            cursor = QTextCursor(block)
            cursor.setPosition(block.position() + start_pos)
            cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor, end_pos - start_pos)

            # 滚动到当前匹配项
            self.log_display.setTextCursor(cursor)
            self.log_display.ensureCursorVisible()

            # 构建当前高亮
            self._current_selection = QTextEdit.ExtraSelection()
            self._current_selection.cursor = cursor
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#ff99cc"))  # 当前匹配高亮颜色
            self._current_selection.format = fmt

            # 合并所有高亮
            extras = [self._current_selection] + self._all_match_selections
            self.log_display.setExtraSelections(extras)

        self.update_search_status()

    def update_search_status(self):
        total = len(self.search_results)
        current = self.current_result_index + 1 if total else 0
        self.search_status_label.setText(f"{current}/{total}")

    def toggle_log_refresh(self):
        if self.log_timer.isActive():
            self.log_timer.stop()
            self.toggle_log_btn.setText("🟢 开始刷新")
        else:
            self.log_timer.start()
            self.toggle_log_btn.setText("🛑 停止刷新")

    def format_json(self):
        raw = self.json_input.toPlainText()
        try:
            parsed = json.loads(raw)
            self.json_input.setPlainText(json.dumps(parsed, indent=4, ensure_ascii=False))
        except json.JSONDecodeError:
            QMessageBox.warning(self, "警告", "无效的JSON格式")

    def get_stylesheet(self):
        return """
            QMainWindow { background-color: #f8f9fa; font-family: "微软雅黑"; }
            QComboBox {
                padding: 8px 10px;
                border-radius: 6px;
                border: 1px solid #ccc;
                background: white;
                font-size: 14px;
                min-height: 36px;
            }
            QPushButton {
                padding: 6px 8px;
                border-radius: 6px;
                border: 1px solid #0078d7;
                background-color: #0078d7;
                color: white;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #3399ff; }
            QPushButton:pressed { background-color: #005a9e; }
            QLineEdit, QPlainTextEdit, QTextEdit {
                background-color: #ffffff;
                border: 1px solid #ccc;
                padding: 8px;
                border-radius: 6px;
                font-size: 14px;
            }
            QLabel {
                font-weight: bold;
                font-size: 16px;
                color: #333333;
            }
        """

class ServiceWorker(QThread):
    finished = pyqtSignal(int, dict)
    error = pyqtSignal(str)

    def __init__(self, service_tester, service_path, data_list):
        super().__init__()
        self.service_tester = service_tester
        self.service_path = service_path
        self.data_list = data_list

    def run(self):
        try:
            for idx, result in self.service_tester.test(self.service_path, self.data_list):
                self.finished.emit(idx, result)
        except Exception as e:
            self.error.emit(str(e))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = JSONServiceTester(
        '''
        {"data":{
            "timestamp":null,
            "service_id":"null"
        }}
        '''
    )
    window.show()
    sys.exit(app.exec_())
