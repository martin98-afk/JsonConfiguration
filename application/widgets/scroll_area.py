from PyQt5.QtWidgets import QScrollArea, QApplication
from PyQt5.QtCore import Qt, QEvent


class WheelScrollArea(QScrollArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def wheelEvent(self, event):
        # 让鼠标滚轮控制横向滚动
        delta = event.angleDelta().y()
        scroll_bar = self.horizontalScrollBar()
        scroll_bar.setValue(scroll_bar.value() - delta)
        event.accept()
