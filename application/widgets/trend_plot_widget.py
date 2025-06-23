import json
from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QRectF
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QGraphicsItem
from loguru import logger

from application.dialogs.service_test_dialog import JSONServiceTester
from application.widgets.persistent_tooltip import PersistentToolTip

# 启用 OpenGL 硬件加速与抗锯齿
pg.setConfigOptions(useOpenGL=True, antialias=True)


class PixelAlignedLinearRegionItem(pg.LinearRegionItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 开启设备坐标缓存
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

    def boundingRect(self):
        r = super().boundingRect()
        # 缩紧到整数像素范围
        return QRectF(round(r.x()), round(r.y()), round(r.width()), round(r.height()))

    def paint(self, p, *args):
        # 使用重载后的 boundingRect 作为裁剪
        p.setClipRect(self.boundingRect())
        super().paint(p, *args)

    def setRegion(self, region):
        self.prepareGeometryChange()
        super().setRegion(region)


class TrendPlotWidget(pg.PlotWidget):
    range_selected = pyqtSignal(datetime, datetime)
    selection_started = pyqtSignal()

    def __init__(self, legend: bool = True, **kwargs):
        super().__init__()
        self.kwargs = kwargs
        # 状态与缓存
        self.tooltip_widget = PersistentToolTip(self)
        self.tooltip_timer = QTimer(self, interval=200)
        self.tooltip_timer.timeout.connect(self._on_tooltip_timer)
        self._last_ts = None
        self._tooltip_active = False
        vb = self.plotItem.vb
        vb.setAutoPan(x=False, y=False)
        # 基础绘图
        self.setBackground('w')
        self.showGrid(x=True, y=True, alpha=0.3)
        self.setMouseEnabled(x=True, y=False)
        if legend:
            self.addLegend(offset=(1, 1))

        # 时间轴
        axis = pg.DateAxisItem(orientation='bottom')
        axis.setStyle(tickTextOffset=10, tickFont=QFont("Microsoft YaHei", 9))
        axis.setTickSpacing(major=3600 * 6, minor=3600)
        self.setAxisItems({'bottom': axis})

        # 区域选择
        self.region = pg.LinearRegionItem(brush=(0, 200, 0, 100), pen=QColor(0, 200, 0))
        self.region.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.region.setZValue(1000)
        self.region.hide()
        self.plotItem.vb.addItem(self.region)

        # 十字光标
        self.crosshair = pg.InfiniteLine(
            angle=90,
            pen=pg.mkPen(QColor('#999999'), width=1, style=Qt.DashLine)
        )
        self.crosshair.setZValue(1001)
        self.crosshair.hide()
        self.plotItem.vb.addItem(self.crosshair)

        # 曲线存储
        self.curves = []
        # 同时清除所有其他项，如文本标签、图例等
        for item in self.items():
            if not isinstance(item, pg.AxisItem) and not isinstance(item, pg.GridItem):
                self.removeItem(item)

        # 交互绑定
        self.scene().sigMouseMoved.connect(self._on_mouse_move)

        # 初始视野
        self._init_xrange = None
        self._init_yrange = None

        # 区域选择状态
        self._is_selecting = False
        self._select_start = None

    def wheelEvent(self, ev):
        vb = self.plotItem.vb
        # 平滑的缩放因子
        factor = 0.92 if ev.angleDelta().y() > 0 else 1.08
        mp = vb.mapSceneToView(ev.pos())
        # 应用缩放，仅在x轴方向
        vb.scaleBy((factor, 1.0), center=(mp.x(), mp.y()))
        ev.accept()

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.autoRange()
            ev.accept()
        else:
            super().mouseDoubleClickEvent(ev)

    def plot_multiple(self, data, mode: str = "line"):
        # 清除并批量添加曲线
        for c in self.curves:
            self.plotItem.removeItem(c)
        self.curves.clear()
        all_y = []
        x = None
        for i, (tag, points) in enumerate(data.items()):
            if not points:
                continue
            x, y = points
            # 动态生成颜色
            hue = i / len(data)
            qcolor = QColor.fromHsvF(hue, 0.7, 0.9)
            color_str = qcolor.name()
            if mode == "fill":
                curve = pg.PlotDataItem(
                    x=x, y=y,
                    pen=pg.mkPen(color_str, width=2),
                    name=tag,
                    **{
                        "fillLevel": min(y),
                        "fillBrush": pg.mkBrush(
                            QColor(color_str).lighter(180)
                        )
                    }
                )
            elif mode == "line":
                curve = pg.PlotDataItem(
                    x=x, y=y,
                    pen=pg.mkPen(color_str, width=2),
                    name=tag,
                    symbol=None
                )
            elif mode == "scatter":
                curve = pg.ScatterPlotItem(
                    x=x, y=y,
                    pen=pg.mkPen(color_str, width=2),
                    name=tag,
                    **{
                        "symbol": "o",
                        "brush": pg.mkBrush(color_str),
                        "size": 5,
                    }
                )
            else:
                logger.error(f"Invalid mode: {mode}")
                raise ValueError
            if mode != "scatter":
                curve.setDownsampling(auto=True, method='peak')
                curve.setClipToView(True)
            curve.setZValue(0)  # 保证曲线在最下面
            self.plotItem.addItem(curve)
            self.curves.append(curve)
            all_y.append(np.array(y))

        if x is not None:
            self.plotItem.setXRange(x[0] - 2500, x[-1] + 1000, padding=0)

        # Y 轴范围及留白
        if all_y:
            arr = np.hstack(all_y)
            mn, mx = arr.min(), arr.max()
            pad = (mx - mn) * 0.1
            self.plotItem.vb.setYRange(mn - pad, mx + pad, padding=0)

        # 确保 region 与 crosshair 在最上层
        self.region.setZValue(1000)
        self.crosshair.setZValue(1001)

    def _on_mouse_move(self, pos):
        mp = self.plotItem.vb.mapSceneToView(pos)
        if not self.viewRect().contains(mp):
            self.crosshair.hide()
            self._stop_tooltip()
            return
        self.crosshair.setPos(mp.x())
        self.crosshair.show()
        self._start_tooltip(mp.x())

    def _start_tooltip(self, ts):
        if ts < 0:
            return
        if self._last_ts is not None and abs(ts - self._last_ts) < 0.5:
            return
        self._last_ts = ts
        if not self._tooltip_active:
            self._tooltip_active = True
            self.tooltip_timer.start()
        self._update_tooltip()

    def _on_tooltip_timer(self):
        if self._tooltip_active:
            self._update_tooltip()
        else:
            self.tooltip_timer.stop()

    def _update_tooltip(self):
        try:
            ts = self._last_ts
            if ts is None:
                return

            tstr = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            lines = [
                f"<div style='font-size:13px; font-weight:bold; margin-bottom:8px;'>🕒 {tstr}</div>",
                "<div style='height:6px;'></div>",  # 垂直间距
                "<table style='border-collapse:collapse; font-size:12px;'>",
            ]

            for curve in self.curves:
                x, y = curve.getData()
                if x is None or len(x) == 0:
                    continue
                idx = np.searchsorted(x, ts)
                idx = min(max(idx, 0), len(x) - 1)
                if abs(x[idx - 1] - ts) < abs(x[idx] - ts):
                    idx -= 1
                if abs(x[idx] - ts) <= 1200:
                    color = curve.opts["pen"].color().name()
                    value_str = f"{y[idx]:.2f}"
                    # 可在此加单位，如 "°C"
                    lines.append(
                        f"""
                        <tr style="line-height: 1.2;">
                            <td style="padding-right:6px;">
                                <span style="color:{color}; font-size:14px;">&#9679;</span>
                            </td>
                            <td style="padding-right:6px; color:#444;">{curve.name()}</td>
                            <td style="font-weight:bold; color:#222;">{value_str}</td>
                        </tr>
                        """
                    )

            lines.append("</table>")
            self.tooltip_widget.show_tooltip("".join(lines))
        except Exception as e:
            logger.error(f"工具提示更新错误: {e}")

    def _stop_tooltip(self):
        self._tooltip_active = False
        self.tooltip_timer.stop()
        self.tooltip_widget.hide()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton and self.kwargs.get("show_service", True):
            self._show_copy_dialog(ev.pos())
            return

        if not self._is_selecting or ev.button() != Qt.LeftButton:
            return super().mousePressEvent(ev)

        # —— 正确映射 —— #
        # 1) widget -> scene
        scenePos = self.mapToScene(ev.pos())
        # 2) scene -> view/data
        x = self.plotItem.vb.mapSceneToView(scenePos).x()

        if self._select_start is None:
            self._select_start = x
            self.region.setRegion([x, x])
            self.region.show()
            self.selection_started.emit()
        else:
            s, e = sorted([self._select_start, x])
            self._select_start = None
            self.region.setRegion([s, e])
            dt0, dt1 = datetime.fromtimestamp(s), datetime.fromtimestamp(e)
            self.range_selected.emit(dt0, dt1)

    def mouseMoveEvent(self, ev):
        if self._is_selecting and self._select_start is not None:
            # 同样的两步映射
            scenePos = self.mapToScene(ev.pos())
            cur = self.plotItem.vb.mapSceneToView(scenePos).x()
            self.region.setRegion([self._select_start, cur])
        super().mouseMoveEvent(ev)

    def enable_selection(self):
        self._is_selecting = True
        self.setCursor(Qt.CrossCursor)

    def disable_selection(self):
        self._is_selecting = False
        self._select_start = None
        self.region.hide()
        self.setCursor(Qt.ArrowCursor)

    def enterEvent(self, ev):
        self._tooltip_active = True
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._stop_tooltip()
        super().leaveEvent(ev)

    def clear_all(self):
        for c in self.curves:
            self.plotItem.removeItem(c)
        self.curves.clear()
        # self._last_indices.clear()

    def showEvent(self, ev):
        super().showEvent(ev)
        # 强制触发重新绘制，激活 GL 上下文
        self.plotItem.vb.update()

    def _show_copy_dialog(self, pos):
        vb = self.plotItem.vb
        mp = vb.mapSceneToView(self.mapToScene(pos))
        ts = mp.x()

        res = {}
        for curve in self.curves:
            x, y = curve.getData()
            if len(x) == 0:
                continue
            idx = int(np.abs(np.array(x) - ts).argmin())
            res[curve.name()] = float(y[idx])

        if res:
            json_str = json.dumps({"data": res}, ensure_ascii=False)
            self.dialog = JSONServiceTester(json_str, parent=self.kwargs.get("parent"))
            self.dialog.show()

    def autoRangeEnabled(self):
        """补丁：代理到内部的 ViewBox.autoRangeEnabled()"""
        return self.plotItem.vb.autoRangeEnabled()
