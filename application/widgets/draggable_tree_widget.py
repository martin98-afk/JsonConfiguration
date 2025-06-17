from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDrag
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QHeaderView
)
from PyQt5.QtWidgets import QProxyStyle, QStyle
from PyQt5.QtWidgets import (
    QTreeWidget
)


class CustomDropIndicatorStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget):
        if element == QStyle.PE_IndicatorItemViewItemDrop and option:
            painter.save()
            rect = option.rect
            # 判断是插入为兄弟节点（上方插入）还是子节点（item展开中）
            is_insert_between = rect.height() <= 2  # Qt 给“插入之间”指示线高度是 1 或 2 像素

            if is_insert_between:
                # 插入为兄弟节点：画显眼蓝色横线
                pen = QPen(QColor("#0078D7"))
                pen.setWidth(4)
                painter.setPen(pen)
                painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
            else:
                # 插入为子节点：画蓝色虚线矩形框
                pen = QPen(QColor("#00AAFF"))
                pen.setStyle(Qt.DashLine)
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawRect(rect.adjusted(1, 1, -1, -1))
            painter.restore()
        else:
            super().drawPrimitive(element, option, painter, widget)


class DraggableTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setStyle(CustomDropIndicatorStyle())
        self.setDropIndicatorShown(True)  # 显示插入指示线
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.header().sectionDoubleClicked.connect(self.on_header_double_clicked)

    def on_header_double_clicked(self, index):
        expanded = (
            not self.topLevelItem(0).isExpanded()
            if self.topLevelItemCount() > 0
            else True
        )
        arrow = "▼" if expanded else "▲"
        self.headerItem()
        self.headerItem().setText(0, f"{self.headerItem().text(0).split(' ')[0]} {arrow}")
        for i in range(self.topLevelItemCount()):
            self.set_item_expanded_recursive(self.topLevelItem(i), expanded)

    def set_item_expanded_recursive(self, item, expand):
        item.setExpanded(expand)
        for i in range(item.childCount()):
            self.set_item_expanded_recursive(item.child(i), expand)

    def startDrag(self, supportedActions):
        # 使用默认拖动逻辑但不设置放大的预览图像
        drag = QDrag(self)
        item = self.currentItem()
        if item:
            mime_data = self.model().mimeData(self.selectedIndexes())
            drag.setMimeData(mime_data)
            # 不设置 drag.setPixmap(...)，这样就没有放大字体的效果
            drag.exec_(supportedActions, Qt.MoveAction)

    def dropEvent(self, event):
        # 使用默认的 drop 行为处理排序
        super().dropEvent(event)

    def setHeaders(self):
        header = self.header()
        self.headerItem().setText(
            0, f"{self.headerItem().text(0)} ▲"
        )
        # 2) 全列都可拖拽调整宽度
        #    如果你只想让部分列可调，把下面这一行注释去掉即可，
        #    然后用 setSectionResizeMode(col, QHeaderView.Interactive) 指定
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
