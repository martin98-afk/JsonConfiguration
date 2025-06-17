import time
import pyqtgraph as pg
from PyQt5.QtCore import Qt, QPointF


class DraggableLine(pg.InfiniteLine):
    """支持非划分状态下长按拖动的红虚线"""
    def __init__(self, x, **kwargs):
        super().__init__(pos=x, angle=90, **kwargs)
        self._press_time = None
        self.setZValue(100)  # 确保在线上方

    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)
        if ev.button() == Qt.LeftButton:
            self._press_time = time.time()
        # 不调用 ev.accept，以便基类能处理移动初始化

    def mouseDragEvent(self, ev):
        # 长按后允许拖动
        if self._press_time and time.time() - self._press_time >= 0.2:
            super().mouseDragEvent(ev)
        else:
            ev.ignore()

    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        self._press_time = None


