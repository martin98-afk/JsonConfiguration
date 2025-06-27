import html
import json
import re
import sys
from collections import deque

from PyQt5.QtCore import Qt, QTimer, QThreadPool
from PyQt5.QtGui import QFont, QTextCursor, QColor, QTextCharFormat, QKeySequence, QTextDocument
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QPlainTextEdit,
    QTextEdit,
    QComboBox,
    QLabel,
    QSplitter,
    QMessageBox,
    QLineEdit,
    QShortcut,
)
from loguru import logger

from application.tools.api_service.servicves_test import ServicesTest
from application.utils.threading_utils import Worker
from application.utils.utils import get_icon, get_button_style_sheet


class JSONServiceTester(QMainWindow):
    LOG_PATTERN = re.compile(
        r"(?P<datetime>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.\d+\s*\|\s*(?P<level>[A-Z]+)\s*\|\s*[^:]+:(?P<func>\w+):\d+\s*-\s*(?P<msg>.*)"
    )

    LEVEL_COLORS = {
        'DEBUG': '#808080',
        'INFO': '#9cdcfe',
        'WARNING': '#ffcb6b',
        'WARN': '#ffcb6b',
        'ERROR': '#f44747',
        'Error': '#f44747',
        'CRITICAL': '#f44747',
    }

    def __init__(self, current_text: str, parent=None):
        super().__init__()
        self._log_warning_shown = None
        self.current_service_id = None
        self.is_loading = False
        self.parent = parent
        self.setWindowTitle("📡 JSON 服务测试工具")
        self.resize(1200, 800)
        self.current_text = current_text or "{}"
        self.search_results = []  # List[Tuple[int, int, int]]
        self.current_result_index = -1
        self._all_match_selections = []
        self.thread_pool = QThreadPool.globalInstance()
        self.setStyleSheet(self.get_stylesheet())
        self.log_update_queue = deque()  # 日志更新队列
        self.is_processing_queue = False  # 队列处理状态
        # 定时器定期处理日志队列（每100毫秒）
        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self.process_log_queue)
        self.queue_timer.start(100)

        # 初始化服务组件
        try:
            self.service_searcher = (
                parent.config.api_tools.get("service_list", None) if parent else None
            )
            self.service_params = (
                parent.config.api_tools.get("service_params", None) if parent else None
            )
            self.service_tester = ServicesTest()
            self.service_logger = (
                parent.config.api_tools.get("service_logger", None) if parent else None
            )
            self.service_reonline = (
                parent.config.api_tools.get("service_reonline", None) if parent else None
            )
            # 初始化界面
            self.init_ui()
            self.format_json()

        except Exception as e:
            logger.error(f"初始化服务组件失败: {e}")

        # 自动加载服务
        self.load_services()

        # 修改日志刷新频率
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.update_service_logs)
        self.log_timer.start(100)  # 将刷新频率从1000毫秒改为2000毫秒

    def init_ui(self):
        # 主容器设置
        main_container = QWidget()
        self.setCentralWidget(main_container)
        main_layout = QVBoxLayout(main_container)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 应用状态栏提示
        self.statusBar().showMessage("准备就绪 - 请选择服务并发送请求")

        # —— 顶部工具栏 ——
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        service_label = QLabel("📋 选择服务:")
        service_label.setFont(QFont("微软雅黑", 13, QFont.Bold))
        toolbar.addWidget(service_label, 1)

        self.service_combo = QComboBox()
        self.service_combo.setEditable(False)
        self.service_combo.setFont(QFont("微软雅黑", 14))
        self.service_combo.setMinimumHeight(36)
        self.service_combo.setToolTip("选择要测试的服务接口")
        self.service_combo.setStatusTip("选择要测试的服务接口")
        self.service_combo.setPlaceholderText("请选择服务...")
        self.service_combo.setStyleSheet(
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
        self.service_combo.currentIndexChanged.connect(self.on_service_changed)
        toolbar.addWidget(self.service_combo, 3)

        # 添加刷新按钮
        refresh_btn = QPushButton("刷新列表")
        refresh_btn.setIcon(get_icon("change"))
        refresh_btn.setStyleSheet(get_button_style_sheet())
        refresh_btn.setToolTip("刷新服务列表")
        refresh_btn.clicked.connect(self.load_services)
        toolbar.addWidget(refresh_btn)
        reonline_btn = QPushButton("重新上线")
        reonline_btn.setIcon(get_icon("重新上线"))
        reonline_btn.setStyleSheet(get_button_style_sheet())
        reonline_btn.setToolTip("重新上线当前选中服务")
        reonline_btn.setMinimumHeight(36)
        reonline_btn.clicked.connect(self.on_reonline_clicked)
        toolbar.addWidget(reonline_btn)
        toolbar.addStretch()
        main_layout.addLayout(toolbar)

        # —— 请求/结果区域 ——
        input_result_layout = QHBoxLayout()

        # 请求输入区域
        input_container = QWidget()
        input_container.setObjectName("RequestPanel")
        input_inner = QVBoxLayout(input_container)
        input_inner.setContentsMargins(8, 8, 8, 8)

        input_header = QHBoxLayout()
        input_header.addWidget(QLabel("📝 请求数据"))
        input_header.addStretch()

        self.format_btn = QPushButton("")
        self.format_btn.setIcon(get_icon("美化代码"))
        self.format_btn.setMaximumHeight(25)
        self.format_btn.setStyleSheet(get_button_style_sheet())
        self.format_btn.setToolTip("格式化当前JSON")
        copy_btn = QPushButton("")
        copy_btn.setIcon(get_icon("复制"))
        copy_btn.setMaximumHeight(25)
        copy_btn.setStyleSheet(get_button_style_sheet())
        copy_btn.setToolTip("复制当前JSON")
        copy_btn.clicked.connect(self.copy_json)
        input_header.addWidget(self.format_btn)
        input_header.addWidget(copy_btn)
        input_inner.addLayout(input_header)

        self.json_input = QPlainTextEdit()
        self.json_input.setPlaceholderText("在此输入JSON请求数据...")
        self.json_input.setPlainText(self.current_text)
        self.json_input.setFont(QFont("Consolas", 14))
        input_inner.addWidget(self.json_input)

        input_btn = QHBoxLayout()
        input_example_btn = QPushButton("模板")
        input_example_btn.setIcon(get_icon("正文模板"))
        input_example_btn.setToolTip("插入示例JSON请求")
        input_example_btn.setStyleSheet(get_button_style_sheet())
        input_example_btn.clicked.connect(self.insert_example_json)
        input_btn.addWidget(input_example_btn)

        input_inner.addLayout(input_btn)

        # 响应结果区域
        result_container = QWidget()
        result_container.setObjectName("ResponsePanel")
        result_inner = QVBoxLayout(result_container)
        result_inner.setContentsMargins(8, 8, 8, 8)

        result_header = QHBoxLayout()
        result_header.addWidget(QLabel("📊 响应结果"))
        result_header.addStretch()
        result_inner.addLayout(result_header)

        self.result_display = QPlainTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setFont(QFont("Consolas", 14))
        self.result_display.setPlaceholderText("响应结果将显示在这里...")
        result_inner.addWidget(self.result_display)

        self.send_btn = QPushButton("请求")
        self.send_btn.setIcon(get_icon("小火箭"))
        self.send_btn.setStyleSheet(get_button_style_sheet())
        self.send_btn.setToolTip("发送请求到所选服务")
        self.send_btn.setMinimumHeight(36)
        result_inner.addWidget(self.send_btn)

        # 添加面板样式
        for panel in [input_container, result_container]:
            panel.setStyleSheet(
                """
                QWidget[objectName="RequestPanel"], QWidget[objectName="ResponsePanel"] {
                    background-color: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 6px;
                }
                QLabel {
                    font-weight: bold;
                    color: #333;
                }
            """
            )

        input_result_layout.addWidget(input_container, 1)
        input_result_layout.addWidget(result_container, 1)

        # —— 日志区域 ——
        log_container = QWidget()
        log_container.setObjectName("LogPanel")
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(8, 8, 8, 8)

        # 日志标题和工具栏
        log_toolbar = QHBoxLayout()
        log_toolbar.setSpacing(8)

        filter_label = QLabel("📜 服务日志")
        filter_label.setFont(QFont("微软雅黑", 12))
        log_toolbar.addWidget(filter_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入关键字搜索日志...")
        self.search_input.setFont(QFont("Consolas", 12))
        self.search_input.setMinimumHeight(32)
        self.search_input.setToolTip("支持多个关键字，空格分隔")
        log_toolbar.addWidget(self.search_input, 4)

        # 导航按钮美化
        self.search_up_btn = QPushButton("▲")
        self.search_up_btn.setStyleSheet(get_button_style_sheet())
        self.search_down_btn = QPushButton("▼")
        self.search_down_btn.setStyleSheet(get_button_style_sheet())
        for btn in (self.search_up_btn, self.search_down_btn):
            btn.setFixedSize(32, 32)
            btn.setFont(QFont("微软雅黑", 10))
            btn.setToolTip("上一个/下一个匹配项")
            log_toolbar.addWidget(btn)

        self.search_status_label = QLabel("0/0")
        self.search_status_label.setFont(QFont("微软雅黑", 12))
        log_toolbar.addWidget(self.search_status_label)

        log_toolbar.addStretch()

        # 自动刷新切换按钮
        self.toggle_log_btn = QPushButton()
        self.toggle_log_btn.setFont(QFont("微软雅黑", 12))
        self.toggle_log_btn.setMinimumHeight(32)
        self.toggle_log_btn.setToolTip("开启/停止自动刷新日志")
        self.toggle_log_btn.setText("🛑 停止刷新")
        self.toggle_log_btn.setStyleSheet(get_button_style_sheet())

        log_toolbar.addWidget(self.toggle_log_btn)

        log_layout.addLayout(log_toolbar)

        # 日志显示区域
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 11))
        self.log_display.setPlaceholderText("日志内容将显示在这里...")
        self.log_display.setStyleSheet(
            """
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, Courier, monospace;
                font-size: 12pt;
                border: none;
            }
            /* 纵向滚动条 */
            QTextEdit QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 0px;
            }
            QTextEdit QScrollBar::handle:vertical {
                background: #555555;
                border-radius: 4px;
                min-height: 20px;
            }
            QTextEdit QScrollBar::handle:vertical:hover {
                background: #888888;
            }
            QTextEdit QScrollBar::add-line:vertical,
            QTextEdit QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
                border: none;
            }
            QTextEdit QScrollBar::add-page:vertical, QTextEdit QScrollBar::sub-page:vertical {
                background: none;
            }

            /* 横向滚动条 */
            QTextEdit QScrollBar:horizontal {
                background: transparent;
                height: 8px;
                margin: 0px;
            }
            QTextEdit QScrollBar::handle:horizontal {
                background: #555555;
                border-radius: 4px;
                min-width: 20px;
            }
            QTextEdit QScrollBar::handle:horizontal:hover {
                background: #888888;
            }
            QTextEdit QScrollBar::add-line:horizontal,
            QTextEdit QScrollBar::sub-line:horizontal {
                width: 0px;
                background: none;
                border: none;
            }
            QTextEdit QScrollBar::add-page:horizontal, QTextEdit QScrollBar::sub-page:horizontal {
                background: none;
            }
            """
        )
        log_layout.addWidget(self.log_display)

        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(8)  # 增加分隔条宽度，便于拖动
        splitter.setChildrenCollapsible(False)  # 防止拖动到极限时子组件消失
        main_layout.addWidget(splitter)

        # 请求/响应容器
        input_result_container = QWidget()
        ir_layout = QVBoxLayout(input_result_container)
        ir_layout.setContentsMargins(0, 0, 0, 0)
        ir_layout.addLayout(input_result_layout)

        # 设置日志面板样式
        log_container.setStyleSheet(
            """
            QWidget[objectName="LogPanel"] {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
            }
        """
        )

        splitter.addWidget(input_result_container)
        splitter.addWidget(log_container)
        splitter.setSizes([400, 400])  # 更平衡的初始分配

        # 信号绑定
        self.format_btn.clicked.connect(self.format_json)
        self.send_btn.clicked.connect(self.send_request)
        self.toggle_log_btn.clicked.connect(self.toggle_log_refresh)
        self.search_input.textChanged.connect(self.on_search_changed)
        self.search_up_btn.clicked.connect(lambda: self.navigate_search(-1))
        self.search_down_btn.clicked.connect(lambda: self.navigate_search(1))

        # 键盘快捷键
        QShortcut(QKeySequence("Ctrl+Return"), self.json_input, self.send_request)
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: self.search_input.setFocus())
        QShortcut(QKeySequence("F3"), self, lambda: self.navigate_search(1))
        QShortcut(QKeySequence("Shift+F3"), self, lambda: self.navigate_search(-1))
        QShortcut(QKeySequence("Ctrl+L"), self, lambda: self.toggle_log_refresh())

    # 新增 on_search_changed
    def on_search_changed(self, text):
        self.apply_filter(text)

    def on_reonline_clicked(self):
        worker = Worker(self.service_reonline.call, self.current_service_id)
        self.thread_pool.start(worker)

    def load_services(self):
        worker = Worker(self.service_searcher.call)
        worker.signals.finished.connect(self.on_services_load)
        self.thread_pool.start(worker)

    def on_services_load(self, services):
        try:
            self.service_combo.clear()
            for name, path, sid in services:
                self.service_combo.addItem(name, userData=(sid, path))
            if self.service_combo.count() > 0:
                self.current_service_id = self.service_combo.itemData(0)[0]
                self.service_combo.setCurrentIndex(0)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载服务失败：{str(e)}")

    def on_service_changed(self):
        if self.service_combo.count() > 0:
            self.current_service_id = self.service_combo.currentData()[0]

    def send_request(self):
        """发送服务请求并处理响应"""
        # 检查服务是否已选择
        if self.service_combo.count() == 0:
            QMessageBox.warning(self, "警告", "没有可用的服务，请先加载服务列表")
            return

        # 获取服务路径
        service_path = self.service_combo.currentData()[1]
        service_name = self.service_combo.currentText()

        # 解析JSON请求数据
        raw_json = self.json_input.toPlainText()
        if not raw_json.strip():
            QMessageBox.warning(self, "警告", "请求数据不能为空")
            return

        try:
            request_data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            QMessageBox.warning(
                self, "JSON格式错误", f"请检查JSON格式是否正确:\n{str(e)}"
            )
            return

        # 更新UI状态
        self.send_btn.setEnabled(False)
        self.send_btn.setText("请求中...")
        self.send_btn.setIcon(get_icon("沙漏"))
        self.statusBar().showMessage(f"正在请求服务: {service_name}...")
        self.result_display.setPlainText("正在处理请求，请稍候...")

        # 异步发送请求
        worker = Worker(self.service_tester._test_single, service_path, request_data)
        worker.signals.finished.connect(self.handle_response)
        worker.signals.error.connect(self.handle_request_error)
        QApplication.processEvents()  # 立即更新UI
        self.thread_pool.start(worker)

    def handle_response(self, result):
        """处理成功的响应结果"""
        try:
            # 恢复按钮状态
            self.send_btn.setEnabled(True)
            self.send_btn.setText("请求")
            self.send_btn.setIcon(get_icon("小火箭"))

            # 格式化显示结果
            if result is None:
                self.result_display.setPlainText("请求成功，但返回了空结果")
                self.statusBar().showMessage("请求完成: 返回空结果", 5000)
                return

            formatted = json.dumps(result, indent=4, ensure_ascii=False)
            self.result_display.setPlainText(formatted)
            self.statusBar().showMessage("请求成功: 已显示结果", 5000)

        except Exception as e:
            # 处理格式化异常
            self.result_display.setPlainText(
                f"返回结果 (无法格式化): {str(result)}\n\n错误: {str(e)}"
            )
            self.statusBar().showMessage("请求成功，但结果格式化失败", 5000)

    def handle_request_error(self, error):
        """处理请求失败的情况"""
        # 恢复按钮状态
        self.send_btn.setEnabled(True)
        self.send_btn.setText("请求")
        self.send_btn.setIcon(get_icon("小火箭"))

        # 显示错误信息
        error_msg = str(error)
        self.result_display.setPlainText(f"请求失败: {error_msg}")

        # 更新状态栏
        self.statusBar().showMessage(
            f"请求失败: {error_msg[:50]}{'...' if len(error_msg) > 50 else ''}", 5000
        )

        # 记录详细错误日志
        logger.error(f"服务请求失败: {error_msg}")

    def update_service_logs(self):
        """优化日志更新逻辑，确保内容完整性"""
        if self.is_loading:
            return

        if self.service_combo.count() == 0 or not self.service_logger:
            if not hasattr(self, "_log_warning_shown"):
                self.log_display.setPlainText("日志服务不可用或未选择服务")
                self._log_warning_shown = True
            return

        try:
            self.is_loading = True
            service_id = self.current_service_id
            if not service_id:
                self.log_display.setPlainText("当前服务没有可用的日志")
                return

            # 执行异步日志获取
            worker = Worker(self.service_logger.call, service_id)
            worker.signals.finished.connect(self.on_loggers_load)
            worker.signals.error.connect(self.handle_log_error)
            self.thread_pool.start(worker)

        except Exception as e:
            self.is_loading = False
            logger.error(f"更新日志异常: {e}")
            self.log_display.setPlainText(f"获取日志时发生错误: {str(e)}")

    def handle_log_error(self, error):
        """处理日志获取失败的情况"""
        self.is_loading = False
        self.log_display.setPlainText(f"获取日志失败: {str(error)}")
        self.statusBar().showMessage("日志获取失败", 3000)

    # 优化后的日志刷新方法
    def on_loggers_load(self, new_log_content):
        self.is_loading = False
        # 将新日志加入队列
        self.log_update_queue.append(new_log_content)

    def process_log_queue(self):
        if not self.log_update_queue or self.is_processing_queue:
            return
        self.is_processing_queue = True
        try:
            # 合并所有待处理日志
            combined_logs = []
            while self.log_update_queue:
                combined_logs.append(self.log_update_queue.popleft())
            # 合并日志内容
            if combined_logs:
                full_log = "\n".join(combined_logs)
                self._update_log_display(full_log)
        finally:
            self.is_processing_queue = False

    def traditional_log_line(self, line: str) -> str:
        safe_line = line.replace(" ", "&nbsp;")  # 替换空格
        for key, value in self.LEVEL_COLORS.items():
            if key in line:
                return f'<span style="color:{value};">{safe_line}</span>'

        return safe_line

    def transform_log_to_html(self, log: str) -> str:
        html_lines = log.splitlines()
        processed_lines = []
        for line in html_lines:
            match = self.LOG_PATTERN.match(line)
            if not match:
                # 这里去掉对空格替换，直接html转义，防止标签被破坏
                safe_line = html.escape(line)
                processed_lines.append(f"<div>{self.traditional_log_line(safe_line)}</div>")
            else:
                parts = match.groupdict()
                time = parts['datetime'][5:]  # MM-DD...
                level = parts['level']
                msg = html.escape(parts['msg'])  # 转义避免标签干扰
                color = self.LEVEL_COLORS.get(level, '#cccccc')
                processed_lines.append(f"<div><span style='color:{color};'>[{time}] | {level} | {msg}</span></div>")

        return f"""
                <div style="white-space: pre-wrap; font-family: Consolas, monospace; font-size: 12pt; margin:0; padding:0;">
                    {''.join(processed_lines)}
                </div>
                """

    def _update_log_display(self, new_log_content):
        if hasattr(self, "_raw_log_content") and new_log_content == self._raw_log_content:
            return
        # 原始增量更新逻辑
        if not hasattr(self, "_raw_log_content"):
            self._raw_log_content = new_log_content
            self.log_display.setHtml(self.transform_log_to_html(new_log_content))
            # 仅在初始化时触发一次滚动
            QTimer.singleShot(0, self.scroll_to_bottom)
            return

        if new_log_content.startswith(self._raw_log_content):
            added_text = new_log_content[len(self._raw_log_content):]
            if added_text.strip():  # 确认有新增内容才插入
                self._raw_log_content = new_log_content
                added_html = self.transform_log_to_html(added_text)
                cursor = self.log_display.textCursor()
                cursor.movePosition(QTextCursor.End)
                cursor.insertHtml(added_html)
                self.log_display.setTextCursor(cursor)
                QTimer.singleShot(0, self.scroll_to_bottom)
            else:
                # 没有新增内容，啥都不做，避免闪烁
                pass
        else:
            # 全量更新时保留滚动位置
            self._raw_log_content = new_log_content
            self.log_display.setHtml(self.transform_log_to_html(new_log_content))
            QTimer.singleShot(0, self.scroll_to_bottom)

    def apply_filter(self, keyword):
        self._all_match_selections.clear()
        self.search_results.clear()
        self.current_result_index = -1

        if not keyword.strip():
            if hasattr(self, "_raw_log_content"):
                self.log_display.setHtml(self._raw_log_content)
            self.update_search_status()
            return

        try:
            keywords = [k.strip() for k in keyword.split() if k.strip()]
            if not keywords:
                return

            highlight_colors = [
                QColor("#ffff00"),
                QColor("#90EE90"),
                QColor("#ADD8E6"),
                QColor("#FFB6C1"),
                QColor("#E6E6FA"),
            ]

            doc = self.log_display.document()

            for idx, kw in enumerate(keywords):
                color = highlight_colors[idx % len(highlight_colors)]
                pos = 0
                while True:
                    cursor = doc.find(kw, pos, QTextDocument.FindCaseSensitively)
                    if cursor.isNull():
                        break
                    sel = QTextEdit.ExtraSelection()
                    sel.cursor = cursor
                    fmt = QTextCharFormat()
                    fmt.setBackground(color)
                    sel.format = fmt
                    self._all_match_selections.append(sel)

                    # 存储基于文档的字符位置
                    self.search_results.append((cursor.selectionStart(), cursor.selectionEnd()))

                    pos = cursor.selectionEnd()

            self.log_display.setExtraSelections(self._all_match_selections)
            self.search_results.sort(key=lambda x: x[0])
            self.update_search_status()

            if self.search_results:
                self.navigate_search(1)

        except Exception as e:
            logger.warning(f"搜索错误：{e}")
            self.statusBar().showMessage(f"搜索错误: {str(e)}", 3000)

    def navigate_search(self, direction):
        if not self.search_results:
            return

        self.current_result_index = (self.current_result_index + direction) % len(self.search_results)
        start, end = self.search_results[self.current_result_index]

        cursor = self.log_display.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)

        self._current_selection = QTextEdit.ExtraSelection()
        self._current_selection.cursor = cursor
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#ff4444"))
        fmt.setForeground(QColor("#ffffff"))
        self._current_selection.format = fmt

        extras = [self._current_selection] + self._all_match_selections
        self.log_display.setExtraSelections(extras)

        self.log_display.setTextCursor(cursor)
        self.log_display.ensureCursorVisible()
        self.update_search_status()

    def scroll_to_bottom(self):
        # 直接定位到文档末尾
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_display.setTextCursor(cursor)
        # 强制滚动条到底部（备用方案）
        sb = self.log_display.verticalScrollBar()
        sb.setValue(sb.maximum())

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
            cursor.movePosition(
                QTextCursor.NextCharacter, QTextCursor.KeepAnchor, len(keyword)
            )
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            fmt = sel.format
            fmt.setBackground(QColor("#ffff00"))
            self._all_match_selections.append(sel)

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

    def insert_example_json(self):
        """插入示例JSON请求"""
        # 异步发送请求
        worker = Worker(self.service_params.call, self.current_service_id)
        worker.signals.finished.connect(self.handle_example_json)
        worker.signals.error.connect(self.handle_request_error)
        self.thread_pool.start(worker)

    def handle_example_json(self, data):
        example = {
            "data": {
                tag: ""
                for tag in data
            }
        }
        try:
            self.json_input.setPlainText(
                json.dumps(example, indent=4, ensure_ascii=False)
            )
            self.statusBar().showMessage("示例JSON已插入", 3000)
        except Exception as e:
            logger.error(f"插入示例JSON失败: {e}")

    def copy_json(self):
        """复制响应结果到剪贴板"""
        text = self.json_input.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.statusBar().showMessage("已复制到剪贴板", 3000)
        else:
            self.statusBar().showMessage("没有可复制的内容", 3000)

    def format_json(self):
        """美化JSON格式"""
        raw = self.json_input.toPlainText()
        try:
            parsed = json.loads(raw)
            self.json_input.setPlainText(
                json.dumps(parsed, indent=4, ensure_ascii=False)
            )
            self.statusBar().showMessage("JSON格式化成功", 3000)
        except json.JSONDecodeError:
            QMessageBox.warning(self, "警告", "无效的JSON格式")
            self.statusBar().showMessage("JSON格式无效，无法格式化", 3000)

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

    def closeEvent(self, event):
        """优雅关闭资源"""
        try:
            if hasattr(self, "log_timer"):
                self.log_timer.stop()
            event.accept()
        except Exception as e:
            logger.warning(f"关闭异常：{e}")
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
