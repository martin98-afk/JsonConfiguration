"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: services_selector_widget.py
@time: 2025/4/27 14:37
@desc: 
"""
from PyQt5.QtCore import Qt, QThreadPool
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QTableWidgetItem,
    QTableWidget, QAbstractItemView, QHeaderView
)


class ServiceSelectorDialog(QDialog):
    """
    Dialog for selecting a service from a fetched list.
    Displays services in a two-column table: service name and URL.
    """
    def __init__(self, fetcher=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择测试服务")
        self.resize(400, 500)
        self.selected_service = None  # tuple (name, url)
        self.fetcher = fetcher
        self._build_ui()
        self._start_fetch()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("双击列表以选择服务"))

        # Use a QTableWidget with two columns: name and URL
        self.table = QTableWidget(self)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["服务名", "调用链接"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.cellDoubleClicked.connect(self._on_cell_double)
        layout.addWidget(self.table)

        btns = QHBoxLayout()
        btns.addStretch()
        ok = QPushButton("确定", self)
        ok.clicked.connect(self.accept)
        cancel = QPushButton("取消", self)
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def _start_fetch(self):
        # Fetch service list asynchronously
        results = self.fetcher._get_services_list()
        # results: List of (name, url)
        self.table.setRowCount(len(results))
        for row, (name, url) in enumerate(results):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(url))

    def _on_cell_double(self, row, column):
        # Triggered on double click, select service
        name_item = self.table.item(row, 0)
        url_item = self.table.item(row, 1)
        if name_item and url_item:
            self.selected_service = (name_item.text(), url_item.text())
            self.accept()

    def get_selected_service(self):
        return self.selected_service
