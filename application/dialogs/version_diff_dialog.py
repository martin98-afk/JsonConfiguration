import ctypes
import json
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QComboBox, QAbstractItemView, QTreeWidgetItemIterator
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QWidget,
    QSizePolicy,
)
from loguru import logger

from application.utils.config_handler import HISTORY_PATH
from application.utils.data_format_transform import list2str
from application.utils.utils import get_icon, get_button_style_sheet


class VersionDiffDialog(QDialog):
    def __init__(
        self,
        history_config: dict,
        current_config: dict,
        apply_to_editor_callback,
        history_file_name: str,
        history_time: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        # 添加窗口标志
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        self.setWindowTitle("历史版本对比")
        self.setMinimumSize(1100, 650)
        # 动态加载 file_map
        self.file_map = self.load_file_map()
        self.history_file_name = history_file_name
        self.selected_file = history_file_name
        self.history_config = history_config
        self.current_config = current_config
        self.apply_to_editor = apply_to_editor_callback
        self.selected_path = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        title = QLabel("← 历史版本      |      当前版本 →")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 18px; margin-bottom: 12px;")
        main_layout.addWidget(title)

        # 顶部文件名和版本时间选择条（横向布局）
        file_version_widget = QWidget()
        file_version_layout = QHBoxLayout()
        file_version_layout.setContentsMargins(0, 0, 0, 0)  # 无内边距
        file_version_layout.setSpacing(6)  # 缩小间距
        file_version_widget.setLayout(file_version_layout)

        file_label = QLabel("📁 文件：")
        file_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.history_file_combo = QComboBox()
        self.history_file_combo.setFixedWidth(230)  # 更宽一点
        self.history_file_combo.setStyleSheet("font-size: 14px; padding: 2px 6px;")
        self.history_file_combo.addItems(self.file_map.keys())
        self.history_file_combo.setCurrentText(history_file_name)
        self.history_file_combo.currentIndexChanged.connect(
            self.update_version_selector
        )

        version_label = QLabel("🕒 版本：")
        version_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; margin-left: 8px;"
        )
        self.version_time_combo = QComboBox()
        self.version_time_combo.setFixedWidth(170)  # 缩小一些
        self.version_time_combo.setStyleSheet("font-size: 14px; padding: 2px 6px;")
        self.version_time_combo.addItems(
            [item[0] for item in self.file_map[history_file_name]]
        )
        self.version_time_combo.setCurrentText(history_time)
        self.version_time_combo.currentIndexChanged.connect(self.load_version_config)

        file_version_layout.addWidget(file_label)
        file_version_layout.addWidget(self.history_file_combo)
        file_version_layout.addWidget(version_label)
        file_version_layout.addWidget(self.version_time_combo)
        file_version_layout.addStretch()

        main_layout.addWidget(file_version_widget)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(8)

        self.history_tree = QTreeWidget()
        self.history_tree.setHeaderLabels(["参数名", "值"])
        self.history_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.history_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.history_tree.setStyleSheet(
            "QTreeWidget { background-color: #f8f8f8; border: 1px solid #ccc; font-size: 14px; }"
        )
        self.history_tree.itemClicked.connect(self.on_history_item_selected)
        body_layout.addWidget(self.history_tree)

        center_button_layout = QVBoxLayout()
        center_button_layout.setSpacing(10)
        center_button_layout.addStretch()

        self.to_current_btn = QPushButton()
        self.to_current_btn.setIcon(get_icon("右箭头"))
        self.to_current_btn.setToolTip("应用到当前")
        self.to_current_btn.setStyleSheet(get_button_style_sheet(bg_color="#66b2ff"))
        self.to_current_btn.setFixedSize(40, 40)
        self.to_current_btn.clicked.connect(self.copy_left_to_right)
        center_button_layout.addWidget(self.to_current_btn)

        self.to_history_btn = QPushButton()
        self.to_history_btn.setIcon(get_icon("左箭头"))
        self.to_history_btn.setToolTip("应用到历史")
        self.to_history_btn.setStyleSheet(get_button_style_sheet(bg_color="#a8e6cf"))
        self.to_history_btn.setFixedSize(40, 40)
        self.to_history_btn.clicked.connect(self.copy_right_to_left)
        center_button_layout.addWidget(self.to_history_btn)

        center_button_layout.addStretch()
        center_widget = QWidget()
        center_widget.setLayout(center_button_layout)
        center_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        body_layout.addWidget(center_widget)

        self.current_tree = QTreeWidget()
        self.current_tree.setHeaderLabels(["参数名", "值"])
        self.current_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.current_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.current_tree.setStyleSheet(
            "QTreeWidget { background-color: #f8f8f8; border: 1px solid #ccc; font-size: 14px; }"
        )
        self.current_tree.itemClicked.connect(self.on_current_item_selected)
        body_layout.addWidget(self.current_tree)

        main_layout.addLayout(body_layout)

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 10, 0, 0)

        self.left_save_btn = QPushButton("保存为历史版本")
        self.left_save_btn.setStyleSheet(get_button_style_sheet(bg_color="#a8e6cf"))
        self.left_save_btn.clicked.connect(self.save_to_history)
        bottom_layout.addWidget(self.left_save_btn)

        self.right_save_btn = QPushButton("加载到当前配置")
        self.right_save_btn.setStyleSheet(get_button_style_sheet(bg_color="#66b2ff"))
        self.right_save_btn.clicked.connect(self.load_to_editor)
        bottom_layout.addWidget(self.right_save_btn)

        main_layout.addLayout(bottom_layout)

        self.load_trees()

    def load_file_map(self):
        import json

        file_map = {}
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
            for file, timestamp, config in history:
                if file not in file_map:
                    file_map[file] = []
                file_map[file].append((timestamp, config))
            for versions in file_map.values():
                versions.sort(
                    key=lambda x: datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S"),
                    reverse=True,
                )
        except Exception as e:
            logger.error("历史文件加载失败:", e)
        return file_map

    def update_version_selector(self):
        self.selected_file = self.history_file_combo.currentText()
        if self.selected_file:
            versions = self.file_map.get(self.selected_file, [])
            version_labels = [f"{ts}" for ts, _ in versions]
            self.version_time_combo.clear()
            self.version_time_combo.addItems(version_labels)

    def load_version_config(self):
        selected_time = self.version_time_combo.currentText()
        if selected_time != "选择历史版本时间":
            version_data = self.get_config_by_version(selected_time)
            self.history_config = version_data
            self.load_trees()

    def get_config_by_version(self, version_time):
        versions = self.file_map.get(self.selected_file, [])
        for ts, config in versions:
            if ts == version_time:
                self.history_file_name = self.selected_file
                return config
        return {}

    def fill_tree(self, tree_widget, data, other_data, path=None, parent=None):
        path = path or []
        for key, value in data.items():
            # 获取另一棵树中对应路径的值
            other_value = self.get_value_by_path(other_data, path + [key])

            # 创建树项
            if isinstance(value, list):
                value = list2str(value)
            if isinstance(other_value, list):
                other_value = list2str(other_value)

            item = QTreeWidgetItem(
                [str(key), str(value) if not isinstance(value, dict) else ""]
            )
            item.setData(0, Qt.UserRole, path + [key])

            # 判断是否有差异（仅比较非字典值或类型不一致时）
            has_difference = False
            if isinstance(value, dict):
                if not isinstance(other_value, dict):
                    has_difference = True  # 类型不同（本节点是字典，对方不是）
            else:
                if isinstance(other_value, dict):
                    has_difference = True  # 类型不同（本节点不是字典，对方是）
                else:
                    has_difference = value != other_value  # 非字典值直接比较

            if has_difference:
                item.setBackground(0, Qt.yellow)  # 高亮差异项背景

            if parent:
                parent.addChild(item)
            else:
                tree_widget.addTopLevelItem(item)

            # 递归处理子节点（仅当当前值为字典时）
            if isinstance(value, dict):
                self.fill_tree(tree_widget, value, other_data, path + [key], item)

    def load_trees(self):
        self.history_tree.clear()
        self.current_tree.clear()

        # 递归填充树并标记差异
        self.fill_tree(self.history_tree, self.history_config, self.current_config)
        self.fill_tree(self.current_tree, self.current_config, self.history_config)

        self.expand_all(self.history_tree)
        self.expand_all(self.current_tree)

    def expand_all(self, tree_widget):
        for i in range(tree_widget.topLevelItemCount()):
            item = tree_widget.topLevelItem(i)
            item.setExpanded(True)
            self.expand_children(item)

    def expand_children(self, item):
        for i in range(item.childCount()):
            child_item = item.child(i)
            child_item.setExpanded(True)
            self.expand_children(child_item)

    def on_history_item_selected(self, item):
        path = item.data(0, Qt.UserRole)
        self.selected_path = path
        self.clear_selection(self.current_tree)
        self.expand_to_path(self.current_tree, path)

    def on_current_item_selected(self, item):
        path = item.data(0, Qt.UserRole)
        self.selected_path = path
        self.clear_selection(self.history_tree)
        self.expand_to_path(self.history_tree, path)

    def clear_selection(self, tree_widget):
        iterator = QTreeWidgetItemIterator(tree_widget)
        while iterator.value():
            iterator.value().setSelected(False)
            iterator += 1

    def expand_to_path(self, tree, path):
        def recurse(node):
            if node.data(0, Qt.UserRole) == path:
                node.setSelected(True)
                tree.scrollToItem(node, QAbstractItemView.PositionAtCenter)
                return True
            for i in range(node.childCount()):
                if recurse(node.child(i)):
                    node.setExpanded(True)
                    return True
            return False

        for i in range(tree.topLevelItemCount()):
            if recurse(tree.topLevelItem(i)):
                break

    def get_value_by_path(self, obj, path):
        for key in path:
            if isinstance(obj, dict) and key in obj:
                obj = obj[key]
            else:
                return None
        return obj

    def set_value_by_path_safe(self, obj, path, value):
        for key in path[:-1]:
            if not isinstance(obj.get(key), dict):
                obj[key] = {}
            obj = obj[key]
        obj[path[-1]] = value

    def copy_left_to_right(self):
        if not self.selected_path:
            return
        value = self.get_value_by_path(self.history_config, self.selected_path)
        self.set_value_by_path_safe(self.current_config, self.selected_path, value)
        self.load_trees()

    def copy_right_to_left(self):
        if not self.selected_path:
            return
        value = self.get_value_by_path(self.current_config, self.selected_path)
        self.set_value_by_path_safe(self.history_config, self.selected_path, value)
        self.load_trees()

    def save_to_history(self):
        from datetime import datetime
        import os

        record = [
            self.history_file_name,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            self.history_config,
        ]
        if os.path.exists(HISTORY_PATH):
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                records = json.load(f)
        else:
            records = []
        records.append(record)
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        with open(self.history_file_name + ".json", "w", encoding="utf-8") as f:
            json.dump(self.history_config, f, ensure_ascii=False, indent=2)

    def load_to_editor(self):
        self.apply_to_editor(self.current_config)

    def nativeEvent(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(message.__int__())
            if msg.message == 0x00A3:
                if self.isMaximized():
                    self.showNormal()
                else:
                    self.showMaximized()
                return True, 0
        return super().nativeEvent(eventType, message)
