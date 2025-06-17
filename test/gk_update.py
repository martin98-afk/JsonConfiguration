import sys
import json
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from datetime import datetime
from openpyxl import Workbook


class JsonEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("工况参数编辑器（优化版）")
        self.resize(1200, 800)
        self.raw_data = {}
        self.current_condition_key = None
        self.frozen_table = None  # 冻结列表格
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout()

        # 左侧：工况表格
        left_widget = QWidget()
        self.left_layout = QVBoxLayout()

        # 冻结列容器
        frozen_container = QWidget()
        frozen_layout = QHBoxLayout(frozen_container)
        self.frozen_table = QTableView()
        self.frozen_table.verticalHeader().hide()
        self.frozen_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.frozen_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.frozen_table.setFocusPolicy(Qt.NoFocus)

        frozen_layout.addWidget(self.frozen_table)

        # 主表格
        self.condition_table = QTableWidget()
        self.condition_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.condition_table.setSelectionMode(QTableWidget.SingleSelection)
        self.condition_table.setSortingEnabled(True)
        self.condition_table.itemClicked.connect(self.on_condition_clicked)

        # 水平滚动条同步
        self.condition_table.horizontalScrollBar().valueChanged.connect(
            lambda value: self.frozen_table.horizontalScrollBar().setValue(value)
        )
        self.frozen_table.horizontalScrollBar().valueChanged.connect(
            lambda value: self.condition_table.horizontalScrollBar().setValue(value)
        )

        # 搜索 + 列设置
        self.setup_search_box()
        self.left_layout.addWidget(frozen_container)
        self.left_layout.addWidget(self.condition_table)
        left_widget.setLayout(self.left_layout)

        # 右侧：统计信息 + 寻优范围
        right_layout = QVBoxLayout()

        # 上部：统计信息表格
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(5)
        self.stats_table.setHorizontalHeaderLabels(["控制参数", "均值", "方差", "样本数", "更新时间"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)

        # 下部：寻优范围表格
        self.range_table = QTableWidget()
        self.range_table.setColumnCount(3)
        self.range_table.setHorizontalHeaderLabels(["控制参数", "下限", "上限"])
        self.range_table.horizontalHeader().setStretchLastSection(True)

        # 操作按钮
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_changes)
        save_as_btn = QPushButton("另存为")
        save_as_btn.clicked.connect(self.save_as_changes)
        import_btn = QPushButton("导入工况")
        import_btn.clicked.connect(self.import_json)
        export_btn = QPushButton("导出为Excel")
        export_btn.clicked.connect(self.export_to_excel)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(import_btn)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(save_as_btn)
        btn_layout.addWidget(export_btn)

        # 组合布局
        right_layout.addWidget(QLabel("控制参数统计信息"))
        right_layout.addWidget(self.stats_table)
        right_layout.addWidget(QLabel("寻优范围设置"))
        right_layout.addWidget(self.range_table)
        right_layout.addLayout(btn_layout)

        # 主分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)
        self.setCentralWidget(splitter)

        # 菜单栏
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("文件")
        import_action = QAction("导入工况", self)
        import_action.triggered.connect(self.import_json)
        file_menu.addAction(import_action)

        save_action = QAction("保存", self)
        save_action.triggered.connect(self.save_changes)
        file_menu.addAction(save_action)

        save_as_action = QAction("另存为", self)
        save_as_action.triggered.connect(self.save_as_changes)
        file_menu.addAction(save_as_action)

        export_action = QAction("导出为Excel", self)
        export_action.triggered.connect(self.export_to_excel)
        file_menu.addAction(export_action)

        self.statusBar().showMessage("就绪")

    def setup_search_box(self):
        """添加搜索框 + 列筛选 + 列设置"""
        search_layout = QHBoxLayout()

        self.search_combo = QComboBox()
        self.search_combo.addItem("全部列")
        self.search_combo.currentIndexChanged.connect(self.filter_table)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("输入关键词过滤工况...")
        self.search_box.textChanged.connect(self.filter_table)

        column_setting_btn = QPushButton("列设置")
        column_setting_btn.clicked.connect(self.show_column_visibility_dialog)

        search_layout.addWidget(QLabel("搜索列:"))
        search_layout.addWidget(self.search_combo)
        search_layout.addWidget(self.search_box)
        search_layout.addWidget(column_setting_btn)
        self.left_layout.insertLayout(0, search_layout)

    def filter_table(self):
        """根据关键词和列筛选过滤表格"""
        keyword = self.search_box.text().strip().lower()
        col_index = self.search_combo.currentIndex() - 1  # -1 表示全部列
        for row in range(self.condition_table.rowCount()):
            visible = False
            for col in range(self.condition_table.columnCount()):
                if col_index != -1 and col != col_index:
                    continue
                item = self.condition_table.item(row, col)
                if item and keyword in item.text().lower():
                    visible = True
                    break
            self.condition_table.setRowHidden(row, not visible)

    def show_column_visibility_dialog(self):
        """列设置对话框"""
        headers = [self.condition_table.horizontalHeaderItem(col).text() for col in
                   range(self.condition_table.columnCount())]
        dialog = ColumnVisibilityDialog(headers, self.condition_table, self)
        dialog.exec_()

    def load_json(self, file_path=None):
        """加载JSON数据"""
        if file_path is None:
            file_path = 'data.json'  # 示例文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.raw_data = json.load(f)
            self.populate_condition_table()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载JSON失败: {str(e)}")

    def import_json(self):
        """导入工况文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择JSON文件", "", "JSON文件 (*.json)")
        if file_path:
            self.load_json(file_path)

    def save_changes(self):
        """保存当前修改"""
        if not self.raw_data:
            return
        try:
            for row in range(self.range_table.rowCount()):
                param = self.range_table.item(row, 0).text()
                lower = float(self.range_table.item(row, 1).text())
                upper = float(self.range_table.item(row, 2).text())
                if self.current_condition_key and param in self.raw_data:
                    data = self.raw_data[param][self.current_condition_key]
                    data[0] = lower
                    data[1] = upper
                    data[5] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open('data.json', 'w', encoding='utf-8') as f:
                json.dump(self.raw_data, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "成功", "数据已保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")

    def save_as_changes(self):
        """另存为新文件"""
        file_path, _ = QFileDialog.getSaveFileName(self, "另存为", "", "JSON文件 (*.json)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.raw_data, f, indent=4, ensure_ascii=False)
                QMessageBox.information(self, "成功", f"数据已保存至 {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"另存失败: {str(e)}")

    def export_to_excel(self):
        """导出为Excel文件"""
        file_path, _ = QFileDialog.getSaveFileName(self, "保存为Excel", "", "Excel文件 (*.xlsx)")
        if not file_path:
            return

        wb = Workbook()
        ws = wb.active

        # 写入表头
        headers = [self.condition_table.horizontalHeaderItem(col).text() for col in
                   range(self.condition_table.columnCount())]
        ws.append(headers)

        # 写入数据
        for row in range(self.condition_table.rowCount()):
            if not self.condition_table.isRowHidden(row):
                row_data = []
                for col in range(self.condition_table.columnCount()):
                    item = self.condition_table.item(row, col)
                    row_data.append(item.text() if item else "")
                ws.append(row_data)

        wb.save(file_path)
        QMessageBox.information(self, "成功", f"数据已导出至 {file_path}")

    def parse_condition(self, condition_str):
        """解析工况字符串"""
        try:
            return json.loads(condition_str)
        except:
            return []

    def extract_headers(self):
        """提取所有唯一的条件参数名作为表头"""
        headers = set()
        for ctrl_param in self.raw_data.values():
            for key_str in ctrl_param:
                if key_str == 'all':
                    continue
                condition = self.parse_condition(key_str)
                for item in condition:
                    if isinstance(item, list) and len(item) >= 2:
                        headers.add(item[0])
        return sorted(headers)

    def populate_condition_table(self):
        """填充工况表格"""
        self.condition_table.setRowCount(0)
        if not self.raw_data:
            return

        # 提取表头
        headers = self.extract_headers()
        self.condition_table.setColumnCount(len(headers))
        self.condition_table.setHorizontalHeaderLabels(headers)

        # 构建数据
        table_data = []
        for ctrl_param in self.raw_data.values():
            for key_str in ctrl_param:
                if key_str == 'all':
                    continue
                condition = self.parse_condition(key_str)
                row = {header: "" for header in headers}
                for item in condition:
                    if isinstance(item, list) and len(item) >= 2:
                        name, value = item[0], item[1]
                        if isinstance(value, list):
                            row[name] = f"[{value[0]:.6f}, {value[1]:.6f}]"
                        else:
                            row[name] = str(value)
                row["key_str"] = key_str
                table_data.append(row)

        self.condition_table.setRowCount(len(table_data))

        for row, row_data in enumerate(table_data):
            for col, header in enumerate(headers):
                item = QTableWidgetItem(row_data.get(header, ""))
                self.condition_table.setItem(row, col, item)
            # 存储 key_str 到 UserRole
            first_item = self.condition_table.item(row, 0)
            if first_item:
                first_item.setData(Qt.UserRole, row_data["key_str"])

        # 设置冻结列
        self.setup_frozen_columns()

        # 列宽自适应
        self.condition_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.frozen_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    def setup_frozen_columns(self):
        """设置冻结列（前3列）"""
        if self.condition_table.columnCount() < 3:
            return
        model = self.condition_table.model()
        self.frozen_table.setModel(model)
        self.frozen_table.setSelectionModel(self.condition_table.selectionModel())
        for col in range(3):  # 冻结前3列
            self.frozen_table.setColumnWidth(col, self.condition_table.columnWidth(col))
        self.frozen_table.setColumnHidden(0, False)
        self.frozen_table.setColumnHidden(1, False)
        self.frozen_table.setColumnHidden(2, False)

    def on_condition_clicked(self, item):
        """处理工况点击事件"""
        row = item.row()
        key_str = self.condition_table.item(row, 0).data(Qt.UserRole)
        self.current_condition_key = key_str
        self.update_stats_table(key_str)
        self.update_range_table(key_str)
        self.statusBar().showMessage(f"已选择工况: {key_str[:30]}...")

    def update_stats_table(self, key_str):
        """更新统计信息表格"""
        self.stats_table.setRowCount(0)
        if not self.raw_data or not key_str:
            return
        for row, (param, data_dict) in enumerate(self.raw_data.items()):
            if key_str in data_dict:
                data = data_dict[key_str]
                self.stats_table.insertRow(row)
                self.stats_table.setItem(row, 0, QTableWidgetItem(param))
                self.stats_table.setItem(row, 1, QTableWidgetItem(str(data[2])))
                self.stats_table.setItem(row, 2, QTableWidgetItem(str(data[3])))
                self.stats_table.setItem(row, 3, QTableWidgetItem(str(data[4])))
                self.stats_table.setItem(row, 4, QTableWidgetItem(str(data[5])))

    def update_range_table(self, key_str):
        """更新寻优范围表格（可编辑）"""
        self.range_table.setRowCount(0)
        if not self.raw_data or not key_str:
            return
        for row, (param, data_dict) in enumerate(self.raw_data.items()):
            if key_str in data_dict:
                data = data_dict[key_str]
                self.range_table.insertRow(row)
                self.range_table.setItem(row, 0, QTableWidgetItem(param))
                lower_item = QTableWidgetItem(str(data[0]))
                upper_item = QTableWidgetItem(str(data[1]))
                lower_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled)
                upper_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled)
                self.range_table.setItem(row, 1, lower_item)
                self.range_table.setItem(row, 2, upper_item)


class ColumnVisibilityDialog(QDialog):
    """列设置对话框"""

    def __init__(self, headers, table, parent=None):
        super().__init__(parent)
        self.headers = headers
        self.table = table
        self.setWindowTitle("列设置")
        layout = QVBoxLayout()
        self.checkboxes = []

        for header in headers:
            cb = QCheckBox(header)
            cb.setChecked(not table.isColumnHidden(headers.index(header)))
            self.checkboxes.append(cb)
            layout.addWidget(cb)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.apply_changes)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
        self.setLayout(layout)

    def apply_changes(self):
        for i, cb in enumerate(self.checkboxes):
            self.table.setColumnHidden(i, not cb.isChecked())
        self.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = JsonEditor()
    window.show()
    sys.exit(app.exec_())
