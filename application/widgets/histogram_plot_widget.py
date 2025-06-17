"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: histogram_plot_widget.py
@time: 2025/5/9 11:46
@desc: 
"""
import pyqtgraph as pg
from PyQt5.QtCore import Qt

from application.widgets.persistent_tooltip import PersistentToolTip


class HistogramPlotWidget(pg.PlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent, background='w')

        # 初始化配置
        self._init_plot()
        self._init_tooltip()

        # 信号连接
        self.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self.viewport().setContextMenuPolicy(Qt.CustomContextMenu)

    def _init_plot(self):
        """初始化图表基本配置"""
        self.showGrid(x=True, y=True)

        # 获取并配置视图框
        vb = self.getViewBox()
        vb.setMouseEnabled(x=True, y=False)  # x轴可拖动，y轴锁定
        vb.setLimits(yMin=0)  # y轴下限限制为0

        # 设置坐标轴标签
        self.getAxis('bottom').setLabel('值')
        self.getAxis('left').setLabel('频数')

    def _init_tooltip(self):
        """初始化自定义tooltip"""
        self.tooltip = PersistentToolTip(self)
        self.tooltip_active = False

    def _on_mouse_moved(self, pos):
        """鼠标移动事件处理"""
        vb = self.getViewBox()
        if vb.sceneBoundingRect().contains(pos):
            self.tooltip_active = True
            x = vb.mapSceneToView(pos).x()
            # 显示 tooltip 在鼠标下方
            self.tooltip.show_tooltip(f"X: {x:.2f}")
        else:
            self.tooltip_active = False
            self.tooltip.hide()

    def leaveEvent(self, event):
        """鼠标离开事件"""
        super().leaveEvent(event)
        self.tooltip.hide()
        self.tooltip_active = False
