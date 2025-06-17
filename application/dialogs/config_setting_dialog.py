import os
import sys

import yaml
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QTreeWidgetItem,
    QLineEdit,
    QStyledItemDelegate,
    QMenu,
    QInputDialog,
    QShortcut,
    QFileDialog,
    QButtonGroup,
)

from application.utils.utils import get_icon, get_button_style_sheet
from application.widgets.draggable_tree_widget import DraggableTreeWidget


class TreeEditDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        editor.setStyleSheet("""
            background-color: white;
            color: #333;
            border: 1px solid #409EFF;
            padding: 3px;
            font-size: 13px;
        """)
        return editor

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect.adjusted(0, 0, 0, 20))


class ConfigSettingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("配置文件编辑器")
        self.resize(900, 650)
        self.setStyleSheet("""
            QDialog { background: #F5F7FA; }
            QTreeWidget { background: #FFF; border: 1px solid #DCDFE6; font-size: 13px; }
            QLineEdit, QPushButton { font-size: 14px; }
        """)

        self.clipboard_data = None
        tool_layout = QHBoxLayout()
        tool_layout.addStretch(1)
        self.restore_btn = QPushButton("恢复默认")
        self.restore_btn.setIcon(get_icon("初始化配置数据"))
        self.restore_btn.setStyleSheet(get_button_style_sheet(bg_color="#99ccff"))
        self.restore_btn.clicked.connect(self.restore_config)
        tool_layout.addWidget(self.restore_btn)
        self.import_btn = QPushButton("打开配置")
        self.import_btn.setIcon(get_icon("打开文件"))
        self.import_btn.setStyleSheet(get_button_style_sheet())
        self.import_btn.clicked.connect(self.import_config)
        tool_layout.addWidget(self.import_btn)
        self.export_btn = QPushButton("导出配置")
        self.export_btn.setIcon(get_icon("导出配置"))  # 需要准备一个导出图标
        self.export_btn.setStyleSheet(get_button_style_sheet())
        self.export_btn.clicked.connect(self.export_config)
        tool_layout.addWidget(self.export_btn)
        self.save_btn = QPushButton("保存并应用")
        self.save_btn.setIcon(get_icon("save"))
        self.save_btn.setStyleSheet(get_button_style_sheet(bg_color="#a8e6cf"))
        self.save_btn.clicked.connect(self.save_config)
        tool_layout.addWidget(self.save_btn)

        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit(placeholderText="搜索字段…")
        self.search_btn = QPushButton()
        self.search_btn.setIcon(get_icon("search"))
        self.search_btn.setStyleSheet(get_button_style_sheet())
        self.search_btn.clicked.connect(lambda: self.filter_tree(self.search_edit.text()))
        self.search_edit.textChanged.connect(self.filter_tree)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(self.search_btn)

        self.tree = DraggableTreeWidget()
        self.tree.setItemDelegate(TreeEditDelegate())
        self.tree.setHeaderLabels(["字段", "值"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnWidth(0, 300)
        self.tree.setFont(QFont("Microsoft YaHei", 14))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_context_menu)
        self.tree.itemDoubleClicked.connect(self.toggle_expand_collapse)
        self.tree.setHeaders()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        # Add layout for top buttons
        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(8)
        main_layout.addLayout(self.button_layout)  # Insert at the top
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.tree)
        main_layout.addLayout(tool_layout)

        self.load_config()

        QShortcut(QKeySequence("Ctrl+C"), self, self.copy_node)
        QShortcut(QKeySequence("Ctrl+V"), self, self.paste_node)
        QShortcut(QKeySequence("Delete"), self, self.delete_parameter)

    def create_top_buttons(self):
        """Create buttons for each top-level node with mutual-exclusive selection."""
        # 清除旧按钮和按钮组
        while self.button_layout.count():
            child = self.button_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 创建新的按钮组（确保互斥）
        self.button_group = QButtonGroup(self)  # [[7]]
        self.button_group.setExclusive(True)  # 设置互斥模式

        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            tab_name = (
                list(self.parent.config.tab_names.values())[i]
                if self.parent.config.tab_names
                else root.child(i).text(0)
            )
            ori_name = (
                list(self.parent.config.tab_names.keys())[i]
                if self.parent.config.tab_names
                else root.child(i).text(0)
            )
            btn = QPushButton(tab_name)
            btn.setCheckable(True)
            btn.setStyleSheet(
                get_button_style_sheet()
                + """
                QPushButton:checked {
                    color: #0078D7;  /* 选中时文字颜色 */
                    font-weight: bold;  /* 加粗 */
                    background-color: #E3F2FD;  /* 选中时背景色 */
                }
            """
            )
            # 绑定点击事件（传递按钮和键名）
            btn.clicked.connect(
                lambda _, b=btn, key=ori_name: self.handle_button_click(b, key)
            )
            self.button_group.addButton(btn)  # 添加到按钮组 [[7]]
            self.button_layout.addWidget(btn)

        # 添加右侧拉伸保持左对齐
        self.button_layout.addStretch()

        # 默认选中第一个按钮
        if root.childCount() > 0:
            first_key = (
                list(self.parent.config.tab_names.keys())[0]
                if self.parent.config.tab_names
                else root.child(0).text(0)
            )
            first_btn = self.button_group.buttons()[0]
            first_btn.setChecked(True)  # 初始选中第一个按钮
            self.show_subtree(first_key)  # 展示对应子树

    def handle_button_click(self, button, key):
        """处理按钮点击事件，确保互斥选中"""
        if button.isChecked():
            self.show_subtree(key)  # 显示对应子树
        else:
            button.setChecked(True)  # 强制保持选中（防止取消选中）

    def show_subtree(self, key):
        """Display only the subtree under the selected top-level node."""
        root = self.tree.invisibleRootItem()
        self.tree.blockSignals(True)

        # Hide all top-level nodes except the selected one
        for i in range(root.childCount()):
            item = root.child(i)
            item.setHidden(item.text(0) != key)

        # Expand the selected node
        self.tree.collapseAll()
        for i in range(root.childCount()):
            item = root.child(i)
            if not item.isHidden():
                self.tree.expandItem(item)
                break

        self.tree.blockSignals(False)

    def restore_config(self):
        self.parent.config.restore_default_params()
        self.parent.config.params_loaded.connect(self.on_config_loaded)
        self.parent.config.load_async()

    def on_config_loaded(self):
        with open(self.parent.config.param_definitions_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        self.tree.clear()
        self.build_tree(data)
        self.create_top_buttons()  # Update buttons after restore

    def import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入配置文件", "", "YAML 文件 (*.yaml *.yml);;所有文件 (*)")
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                self.tree.clear()
                self.build_tree(data)
                self.parent.config.param_definitions_path = path
                self.parent.config.load_async()
                QMessageBox.information(self, "导入成功", f"成功导入配置文件：{os.path.basename(path)}")
            except Exception as e:
                QMessageBox.critical(self, "导入失败", f"导入配置失败：{e}")
        self.create_top_buttons()  # Update buttons after restore

    def toggle_expand_collapse(self, item, col):
        item.setExpanded(not item.isExpanded())

    def on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        menu = QMenu()
        menu.addAction("新增参数", self.add_parameter)
        submenu = menu.addMenu("新增预制参数类型")
        default_templates = self.parent.config.param_templates
        for template_name, template in default_templates.items():
            submenu.addAction(
                template.get("name", template_name),
                lambda template_name=template_name, template=template: self.add_default_param(
                    item, template_name, template
                ),
            )
        menu.addAction("复制节点", self.copy_node)
        menu.addAction("粘贴为子节点", self.paste_node)
        menu.addAction("删除节点", self.delete_parameter)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def add_default_param(self, parent, type, template):
        if parent.data(0, Qt.UserRole) not in ("dict", "list"):
            QMessageBox.warning(self, "操作错误", "只能在字典或列表下新增")
            return
        default_data = {"type": type} | {
            param: param_default
            for param, param_default in zip(
                template.get("params", []), template.get("params_default", [""] * len(template.get("params", [])))
            )
        }
        key, ok = QInputDialog.getText(self, "输入键名", f"请输入 {template.get('name')} 参数名称")
        if not ok or not key:
            return
        new_item = self.create_item(parent, key, default_data)
        self.build_tree(default_data, new_item)
        parent.setExpanded(True)

    def copy_node(self):
        item = self.tree.currentItem()
        if item:
            self.clipboard_data = self._serialize_item(item)

    def paste_node(self):
        parent = self.tree.currentItem()
        if parent and self.clipboard_data:
            if parent.data(0, Qt.UserRole) not in ("dict", "list"):
                QMessageBox.warning(self, "操作错误", "只能粘贴到字典或列表类型下！")
                return
            self._paste_data(parent, self.clipboard_data)

    def _serialize_item(self, item):
        data = {
            'key': item.text(0),
            'value': item.text(1),
            'type': item.data(0, Qt.UserRole),
            'children': [self._serialize_item(item.child(i)) for i in range(item.childCount())]
        }
        return data

    def _paste_data(self, parent, data):
        key = data['key']
        val_type = data['type']
        val = {} if val_type == 'dict' else [] if val_type == 'list' else data['value']
        new_item = self.create_item(parent, key, val)
        if val_type not in ('dict', 'list'):
            new_item.setText(1, str(val))
        for child_data in data['children']:
            self._paste_data(new_item, child_data)
        parent.setExpanded(True)

    def load_config(self):
        self.tree.clear()
        if os.path.exists(self.parent.config.param_definitions_path):
            with open(self.parent.config.param_definitions_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self.build_tree(data)
        self.create_top_buttons()  # Create buttons after loading

    def build_tree(self, data, parent=None):
        parent = parent or self.tree.invisibleRootItem()
        if isinstance(data, dict):
            for k, v in data.items():
                item = self.create_item(parent, str(k), v)
                self.build_tree(v, item)
        elif isinstance(data, list):
            for i, v in enumerate(data):
                item = self.create_item(parent, f"[{i}]", v)
                self.build_tree(v, item)

    def create_item(self, parent, key, value):
        item = QTreeWidgetItem(parent, [key, "" if isinstance(value, (dict, list)) else str(value)])
        item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsSelectable)
        if isinstance(value, dict):
            item.setIcon(0, QIcon(":/icons/folder.png"))
            item.setData(0, Qt.UserRole, "dict")
        elif isinstance(value, list):
            item.setIcon(0, QIcon(":/icons/list.png"))
            item.setData(0, Qt.UserRole, "list")
        else:
            item.setIcon(0, QIcon(":/icons/leaf.png"))
            item.setData(0, Qt.UserRole, type(value).__name__)
        return item

    def save_config(self):
        def item_to_data(item):
            t = item.data(0, Qt.UserRole)
            if t == "dict":
                return {item.child(i).text(0): item_to_data(item.child(i)) for i in range(item.childCount())}
            elif t == "list":
                return [item_to_data(item.child(i)) for i in range(item.childCount())]
            else:
                return item.text(1)

        root = self.tree.invisibleRootItem()
        result = {root.child(i).text(0): item_to_data(root.child(i)) for i in range(root.childCount())}
        with open(self.parent.config.param_definitions_path, "w", encoding="utf-8") as f:
            yaml.dump(result, f, allow_unicode=True, sort_keys=False)
        QMessageBox.information(self, "保存成功", "配置文件已更新！")
        if self.parent:
            self.parent.config.load_async()

    def delete_parameter(self):
        cur = self.tree.currentItem()
        if not cur:
            QMessageBox.warning(self, "操作错误", "请先选中要删除的项！")
            return
        parent = cur.parent() or self.tree.invisibleRootItem()
        rep = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除 '{cur.text(0)}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if rep == QMessageBox.Yes:
            parent.removeChild(cur)
            # 新增逻辑：若从根节点删除，更新顶部按钮
            if parent is self.tree.invisibleRootItem():
                self.create_top_buttons()

    def filter_tree(self, text):
        text = text.lower()

        def recurse(item):
            visible = text in item.text(0).lower() or text in item.text(1).lower()
            for i in range(item.childCount()):
                child = item.child(i)
                if recurse(child):
                    visible = True
            item.setHidden(not visible)
            return visible

        recurse(self.tree.invisibleRootItem())

    def add_parameter(self):
        cur = self.tree.currentItem() or self.tree.invisibleRootItem()
        t = cur.data(0, Qt.UserRole)
        if t not in ("dict", "list"):
            QMessageBox.warning(self, "操作错误", "只能在字典或列表下添加！")
            return
        key = None
        if t == "dict":
            key, ok = QInputDialog.getText(self, "参数键名", "请输入参数名称：")
            if not ok or not key:
                return
        types = {
            "字符串": "",
            "整数": 0,
            "浮点数": 0.0,
            "布尔值": False,
            "字典": {},
            "列表": [],
        }
        ptype, ok = QInputDialog.getItem(
            self, "选择类型", "请选择类型：", list(types.keys()), 0, False
        )
        if not ok:
            return
        val = types[ptype]
        item = self.create_item(cur, key or f"[{cur.childCount()}]", val)
        if not isinstance(val, (dict, list)):
            item.setText(1, str(val))
        cur.setExpanded(True)
        # 新增逻辑：若添加到根节点，更新顶部按钮
        if cur is self.tree.invisibleRootItem():
            self.create_top_buttons()

    def export_config(self):
        # 弹出文件保存对话框，设置默认后缀为.yaml
        path, _ = QFileDialog.getSaveFileName(
                self,
                "导出配置文件",
                "",
                "YAML 文件 (*.yaml *.yml);;所有文件 (*)",
                options=QFileDialog.Options()
            )
        if not path:
            return  # 用户取消操作

        try:
            # 序列化树形数据（复用save_config中的逻辑）
            def item_to_data(item):
                t = item.data(0, Qt.UserRole)
                if t == "dict":
                    return {item.child(i).text(0): item_to_data(item.child(i)) for i in range(item.childCount())}
                elif t == "list":
                    return [item_to_data(item.child(i)) for i in range(item.childCount())]
                else:
                    return item.text(1)

            root = self.tree.invisibleRootItem()
            result = {root.child(i).text(0): item_to_data(root.child(i)) for i in range(root.childCount())}

            # 写入到指定路径
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(result, f, allow_unicode=True, sort_keys=False)

            QMessageBox.information(self, "导出成功", f"配置已保存到：{os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"保存配置时发生错误：{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = ConfigSettingDialog("../../dist/config.yaml")
    dlg.show()
    sys.exit(app.exec_())
