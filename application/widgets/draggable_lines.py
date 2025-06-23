import time
import pyqtgraph as pg
from PyQt5 import QtGui
from PyQt5.QtCore import Qt, QPointF


class DraggableLine(pg.InfiniteLine):
    """支持鼠标悬浮变实线、可拖动的红线"""
    def __init__(self, x, **kwargs):
        super().__init__(pos=x, angle=90, movable=True, **kwargs)
        self._normal_pen = pg.mkPen("r", style=Qt.DashLine, width=2)
        self._hover_pen = pg.mkPen("r", style=Qt.SolidLine, width=3)
        self.setPen(self._normal_pen)
        self.setZValue(100)
        self.setAcceptHoverEvents(True)

    def hoverEvent(self, ev):
        if ev.isEnter():
            self.setPen(self._hover_pen)
        elif ev.isExit():
            self.setPen(self._normal_pen)
