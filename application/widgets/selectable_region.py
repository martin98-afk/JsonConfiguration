from datetime import datetime
from PyQt5.QtCore import Qt
import pyqtgraph as pg

class SelectableRegionItem(pg.LinearRegionItem):
    """
    Single-select region with deep/light fills, correct cursors:
      - Deep fill when idle, light on hover
      - Red/green for unselected/selected
      - Only one region selected
      - Boundary handles ±15px show SizeHorCursor
      - Open hand when idle/hover inside
      - Closed hand only while dragging (mouse down + move)
    """
    _instances = []
    BORDER_TOL_PIXELS = 15

    def __init__(self, index, callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        SelectableRegionItem._instances.append(self)
        self.index = index
        self._changed_callback = callback

        # State
        self.selected = False
        self._hovering_border = False
        self._mouse_pressed = False

        # Brushes
        self.normal_brush         = (255,  50,  50, 120)
        self.normal_hover_brush   = (255, 150, 150,  80)
        self.selected_brush       = ( 50, 200,  50, 120)
        self.selected_hover_brush = (150, 255, 150,  80)
        # Pens
        self.normal_pen         = pg.mkPen((200,  50,  50), width=2)
        self.normal_hover_pen   = pg.mkPen((255, 100, 100), width=3)
        self.selected_pen       = pg.mkPen(( 50, 200,  50), width=2)
        self.selected_hover_pen = pg.mkPen((100, 255, 100), width=3)

        self.setAcceptHoverEvents(True)
        self.setMovable(True)
        self.sigRegionChangeFinished.connect(self._on_change)

        # initial style & cursor
        self.update_style(False)
        self.setCursor(Qt.OpenHandCursor)

    def update_style(self, hover: bool):
        # Fill
        if self.selected:
            brush = self.selected_hover_brush if hover else self.selected_brush
        else:
            brush = self.normal_hover_brush if hover else self.normal_brush
        self.setBrush(brush)
        self.setHoverBrush(brush)
        # Borders
        if self.selected:
            pen = self.selected_hover_pen if hover else self.selected_pen
        else:
            pen = self.normal_hover_pen if hover else self.normal_pen
        for line in self.lines:
            line.setPen(pen)

    def mouseClickEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            # single-select
            for inst in SelectableRegionItem._instances:
                if inst is not self and inst.selected:
                    inst.selected = False
                    inst.update_style(False)
            self.selected = True
            self.update_style(False)
            ev.accept()
        else:
            ev.ignore()

    def hoverMoveEvent(self, ev):
        # detect border proximity
        pos = ev.pos()
        vb = self.getViewBox()
        scene_pos = self.mapToScene(pos)
        x = vb.mapSceneToView(scene_pos).x()
        r0, r1 = self.getRegion()
        xr = vb.viewRange()[0]
        tol = self.BORDER_TOL_PIXELS / (vb.width() / (xr[1] - xr[0]))
        self._hovering_border = abs(x - r0) < tol or abs(x - r1) < tol

        # choose cursor
        if self._mouse_pressed:
            cur = Qt.ClosedHandCursor
        else:
            cur = Qt.SizeHorCursor if self._hovering_border else Qt.OpenHandCursor
        self.setCursor(cur)
        super().hoverMoveEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._mouse_pressed = True
            cur = Qt.SizeHorCursor if self._hovering_border else Qt.ClosedHandCursor
            self.setCursor(cur)
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._mouse_pressed = False
            # restore after release
            cur = Qt.SizeHorCursor if self._hovering_border else Qt.OpenHandCursor
            self.setCursor(cur)
        super().mouseReleaseEvent(ev)

    def hoverEnterEvent(self, ev):
        self.update_style(True)
        cur = Qt.SizeHorCursor if self._hovering_border else Qt.OpenHandCursor
        self.setCursor(cur)
        super().hoverEnterEvent(ev)

    def hoverLeaveEvent(self, ev):
        # always revert to open hand & idle style
        self.update_style(False)
        self.setCursor(Qt.OpenHandCursor)
        super().hoverLeaveEvent(ev)

    def _on_change(self):
        r0, r1 = self.getRegion()
        t0 = datetime.fromtimestamp(r0)
        t1 = datetime.fromtimestamp(r1)
        self._changed_callback(self.index, (t0, t1))
