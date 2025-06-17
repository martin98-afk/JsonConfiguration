import re

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QDialogButtonBox, QTableWidgetItem,
    QTableWidget, QMessageBox
)
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QHeaderView, QSizePolicy
)


class RangeListDialog(QDialog):
    def __init__(self, current_value=""):
        super().__init__()
        self.setWindowTitle("自定义切分范围")
        self.setMinimumSize(400, 300)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)

        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["最小值", "最大值"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setDragDropMode(QTableWidget.InternalMove)
        self.layout.addWidget(self.table, 1)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加区间")
        remove_btn = QPushButton("删除选中")
        for btn in (add_btn, remove_btn):
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #28a745;
                    border-radius: 6px;
                    padding: 6px 12px;
                    color: white;
                }
                QPushButton:hover { background-color: #218838; }
                QPushButton:pressed { background-color: #1e7e34; }
            """)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        self.layout.addLayout(btn_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for btn in (button_box.button(QDialogButtonBox.Ok), button_box.button(QDialogButtonBox.Cancel)):
            btn.setMinimumHeight(32)
        button_box.setStyleSheet("""
            QDialogButtonBox QPushButton {
                background-color: #0078d7;
                border-radius: 6px;
                padding: 6px 12px;
                color: white;
                min-width: 80px;
            }
            QDialogButtonBox QPushButton:hover { background-color: #005a9e; }
            QDialogButtonBox QPushButton:pressed { background-color: #004578; }
        """)
        self.layout.addWidget(button_box)

        add_btn.clicked.connect(self.add_row)
        remove_btn.clicked.connect(self.remove_selected_rows)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)

        if current_value:
            for part in current_value.split(','):
                if '~' in part:
                    a, b = part.split('~')
                    self.add_row(a.strip(), b.strip())
                else:
                    self.add_row(part.strip(), '')
        else:
            self.add_row()

    def add_row(self, min_val="", max_val=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(min_val))
        self.table.setItem(row, 1, QTableWidgetItem(max_val))
        self.table.setCurrentCell(row, 0)

    def remove_selected_rows(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)

    def validate_and_accept(self):
        for row in range(self.table.rowCount()):
            min_item = self.table.item(row, 0)
            max_item = self.table.item(row, 1)
            if not min_item or not max_item:
                continue
            min_text = min_item.text().strip()
            max_text = max_item.text().strip()

            if not self.is_number(min_text) or not self.is_number(max_text):
                self.highlight_error_row(row)
                QMessageBox.warning(self, "输入错误", f"第 {row + 1} 行包含非数值项！")
                return
            if float(max_text) < float(min_text):
                self.highlight_error_row(row)
                QMessageBox.warning(self, "区间错误", f"第 {row + 1} 行最大值小于最小值！")
                return

        self.accept()

    def highlight_error_row(self, row):
        for col in range(2):
            item = self.table.item(row, col)
            if item:
                item.setBackground(Qt.red)

    def is_number(self, val):
        return re.match(r"^-?\d+(\.\d+)?$", val) is not None

    def get_ranges(self):
        ranges = []
        for row in range(self.table.rowCount()):
            min_item = self.table.item(row, 0)
            max_item = self.table.item(row, 1)
            if min_item and max_item:
                min_val = min_item.text().strip()
                max_val = max_item.text().strip()
                if min_val and max_val:
                    ranges.append((min_val, max_val))
        return "\n".join(f"{a} ~ {b}" for a, b in ranges)

    @staticmethod
    def save(key, val):
        vals = []
        val.replace(",", "\n")
        for part in val.split('\n'):
            part = part.strip()
            if '~' in part:
                a, b = part.split('~')
                try:
                    vals.append([float(a.strip()), float(b.strip())])
                except ValueError:
                    continue
        return key, vals

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.add_row()
        elif event.key() == Qt.Key_Delete:
            self.remove_selected_rows()
        elif event.matches(QKeySequence.Paste):
            clipboard = QApplication.clipboard()
            self.paste_ranges(clipboard.text())
        else:
            super().keyPressEvent(event)

    def paste_ranges(self, text):
        lines = text.strip().splitlines()
        count = 0
        for line in lines:
            line = line.strip()
            if "~" in line:
                parts = line.split("~")
                if len(parts) == 2:
                    min_val, max_val = parts[0].strip(), parts[1].strip()
                    self.add_row(min_val, max_val)
                    count += 1
        if count == 0:
            QMessageBox.warning(self, "粘贴失败", "未识别有效的区间格式（如 0~10）")