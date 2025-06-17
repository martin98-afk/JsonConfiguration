"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: persistent_tooltip.py
@time: 2025/5/9 11:46
@desc: 
"""
from PyQt5.QtCore import QPoint
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication


class PersistentToolTip(QWidget):
    """自动适应内容大小的持久化提示框，避免窗口遮挡"""
    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowOpacity(0.9)  # 取值范围 0.0（完全透明）～ 1.0（不透明）
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel("", self)
        self.label.setWordWrap(True)  # 自动换行
        self.label.setStyleSheet("""
            QLabel {
                background-color: #F9F9F9;
                color: #2B2B2B;
                border: 1px solid #D3D3D3;
                border-radius: 6px;
                padding: 8px 12px;
                font-family: 'Microsoft YaHei', sans-serif;
                font-size: 13px;
                font-weight: bold;
            }
        """)

        layout.addWidget(self.label)
        self.hide()

    def show_tooltip(self, text, offset=QPoint(10, 5)):
        self.label.setText(text)
        self.adjustSize()

        screen_rect = QApplication.primaryScreen().availableGeometry()
        pos = QCursor.pos() + offset
        tooltip_rect = QRect(pos, self.size())

        # 检查是否超出屏幕右下边界
        if tooltip_rect.right() > screen_rect.right():
            pos.setX(screen_rect.right() - self.width() - 5)
        if tooltip_rect.bottom() > screen_rect.bottom():
            pos.setY(screen_rect.bottom() - self.height() - 5)

        # 检查是否超出屏幕左上边界
        if pos.x() < screen_rect.left():
            pos.setX(screen_rect.left() + 5)
        if pos.y() < screen_rect.top():
            pos.setY(screen_rect.top() + 5)

        self.move(pos)
        self.show()
