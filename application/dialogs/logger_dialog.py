from collections import deque
from PyQt5.QtGui import QTextCharFormat, QColor, QTextCursor, QFont
from PyQt5.QtWidgets import QPlainTextEdit
from loguru import logger

class QTextEditLogger:
    def __init__(self, text_edit, max_lines=1000):
        self.text_edit = text_edit
        # 缓存最后 max_lines 条日志
        self.buffer = deque(maxlen=max_lines)
        # 级别对应颜色
        self.colors = {
            "DEBUG": QColor("#00BFFF"),
            "INFO": QColor("#00FF7F"),
            "WARNING": QColor("#FFD700"),
            "ERROR": QColor("#FF4500"),
            "CRITICAL": QColor("#FF1493"),
        }

    def write(self, message):
        text = message.strip()
        if not text:
            return
        # 先缓存
        self.buffer.append(text)

        # 如果当前视图可见，就立即输出（实时 + 历史都是同一窗口）
        self._append_line(text)

    def _append_line(self, line):
        # 找到日志级别
        lvl = None
        for k in self.colors:
            if f"| {k} |" in line:
                lvl = k
                break
        fmt = QTextCharFormat()
        fmt.setForeground(self.colors.get(lvl, QColor("#FFFFFF")))

        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(line + "\n", fmt)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

    def flush(self):
        pass
