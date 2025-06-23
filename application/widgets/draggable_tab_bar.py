from PyQt5.QtCore import Qt, QObject, QEvent, QPoint, QMimeData, QSize, QTimer
from PyQt5.QtGui import QDrag, QFontMetrics
from PyQt5.QtWidgets import (
    QToolButton,
    QSizePolicy,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QFrame,
    QVBoxLayout,
    QScrollBar,
)

from application.utils.utils import get_icon, get_button_style_sheet
from application.widgets.scroll_area import WheelScrollArea


class DraggableTabBar(QWidget, QObject):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        QObject.__init__(self)
        self.scale = parent.scale
        self.parent = parent
        self._active_rename = None
        self.setAcceptDrops(True)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(45)
        self.setMaximumHeight(45)
        self.setStyleSheet(
            """
            background-color: #e9ecef;
            border: none;
            """
        )

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(18)
        spacer = QWidget()
        spacer.setFixedWidth(4)
        self.layout.insertWidget(0, spacer)

        self.plus_btn = QPushButton(self)
        self.plus_btn.setIcon(get_icon("add (1)"))
        self.plus_btn.setToolTip("新建配置")
        self.plus_btn.setStyleSheet(get_button_style_sheet())
        self.plus_btn.clicked.connect(self.parent.new_config)
        self.layout.insertWidget(1, self.plus_btn)

        tab_scroll_container = QVBoxLayout()
        tab_scroll_container.setContentsMargins(0, 0, 0, 0)
        tab_scroll_container.setSpacing(0)

        self.custom_scrollbar = QScrollBar(Qt.Horizontal)
        self.custom_scrollbar.setStyleSheet(
            """
            QScrollBar:horizontal {
                height: 4px;
                background: transparent;
                border-radius: 3px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #c0c0c0;
                border-radius: 3px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #0078D7;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """
        )
        # 关键：不隐藏，而是禁用并使其透明，但保留占位
        self.custom_scrollbar.setEnabled(False)
        self.custom_scrollbar.setStyleSheet(
            self.custom_scrollbar.styleSheet()
            + "QScrollBar::handle:horizontal { background: transparent; }"
        )

        # \u6eda\u52a8\u533a\u57df
        self.scroll_area = WheelScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.horizontalScrollBar().rangeChanged.connect(
            self._sync_scrollbar_range
        )

        # \u6807\u7b7e\u5bb9\u5668
        self.tabs_container = QWidget()
        self.tabs_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.tabs_layout = QHBoxLayout(self.tabs_container)
        self.tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs_layout.addStretch(1)

        self.scroll_area.setWidget(self.tabs_container)

        self.custom_scrollbar.valueChanged.connect(
            lambda value: self.scroll_area.horizontalScrollBar().setValue(value)
        )
        self.scroll_area.horizontalScrollBar().valueChanged.connect(
            lambda value: self.custom_scrollbar.setValue(value)
        )

        self.scroll_area.horizontalScrollBar().rangeChanged.connect(
            self._on_range_changed
        )

        tab_scroll_container.addWidget(self.custom_scrollbar)
        tab_scroll_container.addWidget(self.scroll_area)

        # --------- fix 底部距离问题 ---------
        # 用 QWidget 包裱 tab_scroll_container，确保距离点与 scrollbar 精确控制
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addLayout(tab_scroll_container)

        self.layout.addWidget(wrapper, 1)
        spacer = QWidget()
        spacer.setFixedWidth(1)
        self.layout.addWidget(spacer)

    def _on_range_changed(self, min_val, max_val):
        if max_val > 0:
            self.custom_scrollbar.setEnabled(True)
            self.custom_scrollbar.setStyleSheet(self.custom_scrollbar.styleSheet().replace("background: transparent;", "background: #999;"))
        else:
            self.custom_scrollbar.setEnabled(False)
            self.custom_scrollbar.setStyleSheet(self.custom_scrollbar.styleSheet().replace("background: #999;", "background: transparent;"))

    def _sync_scrollbar_range(self, min_value=None, max_value=None):
        hbar = self.scroll_area.horizontalScrollBar()
        self.custom_scrollbar.setRange(hbar.minimum(), hbar.maximum())
        self.custom_scrollbar.setPageStep(hbar.pageStep())

    def add_tab(self, filename):
        """
        新建一个 QFrame 作为“标签页”外壳（container）：
          • 固定高度 40px
          • 根据文件名动态算最小宽度，保证文字不截断
          • 点击 container 任意位置都能切换到该 tab
          • 选中时样式：白底+3px蓝色下边框
          • 未选中时样式：灰底+3px透明下边框
          • 内部布局： [ tab_btn(文字) + stretch + close_btn ]
        """
        from PyQt5.QtGui import QFontMetrics

        # —— 1. 新建 container ——
        container = QFrame(self.tabs_container)
        container.setFrameShape(QFrame.NoFrame)
        container.setFrameShadow(QFrame.Plain)
        container.setObjectName("tab_container")
        container.setProperty("active", False)
        container.setFixedHeight(40)

        # —— 3. 设置选中/未选中样式 ——
        container.setStyleSheet(
            """
            /* 默认态：灰底 + 上圆角 + 下外圆角 + 灰色边框 */
            QFrame {
                background: #d3d6db;
                border: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
                margin-bottom: 3px; /* 给选中态留出下边空间 */
                transition: background 0.2s ease;
            }

            /* 悬浮态：变亮一些，有 hover 效果 */
            QFrame:hover {
                background: #f0f0f0;
            }

            /* 选中态：白底 + 去掉下边框 + 只保留上圆角，看起来像是和下方连起来的 */
            QFrame[active="true"] {
                background: #f5f7fa;
                border-bottom: none; /* 取消底部边界，与下方连通 */
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                margin-bottom: 0px;
            }
        """
        )
        # —— 4. 内部布局 ——
        cont_layout = QHBoxLayout(container)
        cont_layout.setContentsMargins(12, 0, 12, 0)
        cont_layout.setSpacing(16)

        # 获取不重复的文件名
        filename = self.ensure_new_name(filename)
        # —— 5. 文件名按钮 ——
        tab_btn = QPushButton(filename, container)
        tab_btn.setObjectName("tab_btn")
        tab_btn.setCheckable(True)
        tab_btn.setMinimumHeight(36)
        tab_btn.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: none;
                color: #333333;
                font-size: 17px;
                text-align: left;
            }
            QPushButton:hover {
                color: #0050a0;
            }
            QPushButton:checked {
                color: #0078D7;
                font-weight: bold;
            }
            """
        )
        tab_btn.installEventFilter(self)
        tab_btn.setToolTip(
            "<div style='background-color:#f0f0f0; color:#333333; "
            "border:1px solid #cccccc; padding:4px 8px;'>双击可重命名文件</div>"
        )
        tab_btn.clicked.connect(
            lambda _, b=tab_btn: (
                self._finalize_inline_rename(),
                self.set_active_tab(b.text()),
                self.parent.switch_to_file(b.text()),
            )
        )
        font_metrics = QFontMetrics(tab_btn.font())
        text_width = font_metrics.width(filename) + 70  # 文字宽度 + 额外边距
        tab_btn.setMinimumWidth(text_width)
        tab_btn.setMaximumWidth(text_width + 90)  # 控制最大宽度，避免太宽
        tab_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        cont_layout.addWidget(tab_btn)

        # —— 6. 弹性伸缩 ——
        cont_layout.addStretch(1)

        # —— 7. 关闭按钮 ——
        close_btn = QToolButton(container)
        close_btn.setObjectName("close_btn")
        close_btn.setIcon(get_icon("叉号"))
        close_btn.setAutoRaise(True)
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(
            """
            QToolButton {
                background: transparent;
                border: none;
            }
            QToolButton:hover {
                background: #e81123;
                border-radius: 10px;
            }
        """
        )
        close_btn.clicked.connect(
            lambda _, b=tab_btn: (self._finalize_inline_rename(), self._on_close(b))
        )
        cont_layout.addWidget(close_btn)

        # —— 8. container 点击任意位置也能切换 ——
        def container_clicked(event):
            # 动态读取当前 tab_btn 的文本，而不是闭包里“老” filename
            current_btn = container.findChild(QPushButton, "tab_btn")
            if current_btn:
                new_name = current_btn.text()
                self._finalize_inline_rename()
                self.set_active_tab(new_name)
                self.parent.switch_to_file(new_name)

        container.mousePressEvent = container_clicked

        # —— 9. 插入到 tabs_layout 中 ——
        insert_pos = max(0, self.tabs_layout.count() - 1)
        self.tabs_layout.insertWidget(insert_pos, container)

        # —— 10. 刷新几何并选中 ——
        container.update()
        self.tabs_container.updateGeometry()
        self.set_active_tab(filename)

        return filename

    def set_active_tab(self, filename):
        target_widget = None

        for i in range(self.tabs_layout.count()):
            widget = self.tabs_layout.itemAt(i).widget()
            if not widget or not isinstance(widget, QWidget):
                continue

            btn = widget.findChild(QPushButton, "tab_btn")
            if btn and btn.text() == filename:
                btn.setChecked(True)
                widget.setProperty("active", True)
                target_widget = widget
            elif btn:
                btn.setChecked(False)
                widget.setProperty("active", False)

            widget.style().unpolish(widget)
            widget.style().polish(widget)

        if target_widget:
            def ensure_visible():
                scroll_bar = self.scroll_area.horizontalScrollBar()
                widget_x = target_widget.pos().x()
                widget_width = target_widget.width()
                view_width = self.scroll_area.viewport().width()

                # 如果 widget 太靠右
                if widget_x + widget_width > scroll_bar.value() + view_width:
                    scroll_bar.setValue(widget_x + widget_width - view_width)
                # 如果 widget 太靠左
                elif widget_x < scroll_bar.value():
                    scroll_bar.setValue(widget_x)

            # 延迟确保 widget 布局完成
            QTimer.singleShot(0, ensure_visible)

    def rename_tab(self, old_name: str, new_name: str):
        """通过名称找到对应tab，并进行重命名"""
        for i in range(self.tabs_layout.count()):
            widget = self.tabs_layout.itemAt(i).widget()
            if not widget or not isinstance(widget, QWidget):
                continue
            btn = widget.findChild(QPushButton, "tab_btn")
            if btn and btn.text() == old_name:
                btn.setText(new_name)
                self.parent.rename_file(old_name, new_name)

    def _inline_rename(self, btn: QPushButton):
        # 结束已有编辑
        self._finalize_inline_rename()

        old_name = btn.text()
        container = btn.parentWidget()
        layout = container.layout()
        close_btn = container.findChild(QToolButton, "close_btn")

        # 移除并隐藏按钮
        layout.removeWidget(btn)
        layout.removeWidget(close_btn)
        btn.hide()
        close_btn.hide()

        # 内部编辑类
        class InlineEdit(QLineEdit):
            def focusOutEvent(self, e):
                super().focusOutEvent(e)
                finish()

        editor = InlineEdit(old_name, container)
        editor.setFixedHeight(btn.height())
        editor.setFixedWidth(container.width()-26)
        editor.setStyleSheet(
            "QLineEdit {"
            "   background: #f5f7fa;"
            "   border: none;"
            "   padding: 0px 0px;"
            "   color: #0078D7;"
            "   font-size: 17px;"
            "   font-weight: bold;"
            "}"
            "QLineEdit::selected {"
            "   background-color: #CCE4FF;"
            "   color: white;"  # 修改这里：将选中文本的颜色设为白色
            "}"
        )
        editor.setPlaceholderText("输入文件名称")
        layout.addWidget(editor)
        editor.setFocus()
        editor.selectAll()

        finished = False

        def finish():
            nonlocal finished
            if finished:
                return
            finished = True
            new_name = editor.text().strip() or old_name
            # 清理编辑框
            layout.removeWidget(editor)
            editor.deleteLater()
            if new_name == old_name:
                pass
            else:
                # 恢复按钮和关闭
                new_name = self.ensure_new_name(new_name, btn)
                btn.setText(new_name)
                font_metrics = QFontMetrics(btn.font())
                text_width = font_metrics.width(new_name) + 70  # 文字宽度 + 额外边距
                btn.setMinimumWidth(text_width)
                btn.setMaximumWidth(text_width + 90)  # 控制最大宽度，避免太宽

            btn.show()
            close_btn.show()
            # 先把文字按钮加回去，再把关闭按钮加上去
            layout.insertWidget(0, btn)
            layout.addWidget(close_btn)
            # 更新父编辑器
            self.parent.rename_file(old_name, new_name)
            # 更新 Tooltip
            btn.setToolTip(
                "<div style='background-color:#f0f0f0; color:#333333; "
                "border:1px solid #cccccc; padding:4px 8px;'>双击可重命名文件</div>"
            )

        editor.returnPressed.connect(finish)
        self._active_rename = (btn, finish)

    def _finalize_inline_rename(self):
        if self._active_rename:
            btn, finish = self._active_rename
            finish()
            self._active_rename = None

    def eventFilter(self, obj, event):
        if isinstance(obj, QPushButton) and event.type() == QEvent.MouseButtonDblClick:
            self._inline_rename(obj)
            return True
        return super().eventFilter(obj, event)

    def remove_tab_widget(self, filename):
        for i in range(self.tabs_layout.count()):
            w = self.tabs_layout.itemAt(i).widget()
            if w is not None:
                btn = w.findChild(QPushButton)
                if btn and btn.text() == filename:
                    self.tabs_layout.removeWidget(w)
                    w.deleteLater()
                    break

    def ensure_new_name(self, new, ori_btn=None):
        """双击重命名出现相同名称时，自动增加后缀，直到名称唯一"""
        original_name = new
        existing_names = set()

        # 收集所有当前存在的文件名
        for i in range(self.tabs_layout.count()):
            w = self.tabs_layout.itemAt(i).widget()
            if w is not None:
                btn = w.findChild(QPushButton)
                if btn and btn != ori_btn:
                    existing_names.add(btn.text())

        # 如果名称唯一，直接返回
        if new not in existing_names:
            return new

        # 否则不断尝试增加后缀
        count = 1
        while True:
            new = f"{original_name}_{count}"
            if new not in existing_names:
                return new
            count += 1

    def index_of(self, filename) -> int:
        for i in range(self.tabs_layout.count()):
            w = self.tabs_layout.itemAt(i).widget()
            if w is not None:
                btn = w.findChild(QPushButton)
                if btn and btn.text() == filename:
                    return i
        return -1

    def tab_name_at(self, index) -> str:
        if index < 0 or index >= self.tabs_layout.count():
            return None
        w = self.tabs_layout.itemAt(index).widget()
        if w is not None:
            btn = w.findChild(QPushButton)
            return btn.text() if btn else None
        return None

    def all_buttons(self):
        return [
            w.findChild(QPushButton)
            for w in (
                self.tabs_layout.itemAt(i).widget()
                for i in range(self.tabs_layout.count())
            )
            if w is not None and w.findChild(QPushButton)
        ]

    def _on_close(self, btn: QPushButton):
        name = btn.text()
        if hasattr(self.parent, "is_same_as_file") and self.parent.is_same_as_file(
            name
        ):
            self.parent.close_file(name)
        else:
            box = QMessageBox(self)
            box.setWindowTitle(f"关闭文件 - {name}")
            box.setText(f"<h3>文件 '{name}' 已修改</h3>")
            box.setInformativeText("是否保存更改并关闭文件？")

            save_btn = box.addButton("保存", QMessageBox.AcceptRole)
            save_btn.setIcon(get_icon("保存"))
            save_btn.setStyleSheet(get_button_style_sheet())

            discard_btn = box.addButton("不保存", QMessageBox.DestructiveRole)
            discard_btn.setIcon(get_icon("不保存"))
            discard_btn.setStyleSheet(get_button_style_sheet())

            cancel_btn = box.addButton("取消", QMessageBox.RejectRole)
            cancel_btn.setIcon(get_icon("取消"))
            cancel_btn.setStyleSheet(get_button_style_sheet())

            box.exec_()
            clicked = box.clickedButton()
            if clicked == save_btn:
                self.parent.switch_to_file(name)
                self.parent.auto_save()
                self.parent.close_file(name)
            elif clicked == discard_btn:
                self.parent.close_file(name)