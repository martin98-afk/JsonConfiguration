from PyQt5.QtWidgets import (
    QComboBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)

from application.utils.utils import get_icon, get_button_style_sheet


class LoadHistoryDialog(QDialog):
    def __init__(self, file_map, filenames, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择历史记录")
        self.setMinimumSize(500, 180)

        # 设置整体样式
        self.setStyleSheet("""
            QDialog {
                font-family: Arial, sans-serif;
                background-color: #f4f4f9;
            }
            QLabel {
                font-size: 13px;
                color: #222;
            }
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 5px;
                min-width: 100px;
                font-size: 20px;
                background-color: white;
                color: black; /* 默认字体颜色 */
            }
            QComboBox:hover {
                border-color: #40a9ff;
                color: black; /* 鼠标悬浮时字体颜色 */
            }
            QPushButton {
                font-size: 13px;
                background-color: #0078d7;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #004578;
            }
        """)

        self.file_map = file_map
        self.selected_file = None
        self.selected_version = None
        self.selected_config = None
        self.action = None

        # 文件下拉
        self.file_combobox = QComboBox()
        self.file_combobox.addItems(filenames)

        # 版本下拉
        self.version_combobox = QComboBox()

        # 文件+版本 同行布局
        select_layout = QHBoxLayout()
        select_layout.setSpacing(15)

        file_label = QLabel("选择文件：")
        version_label = QLabel("选择版本：")
        file_label.setFixedWidth(65)
        version_label.setFixedWidth(65)

        select_layout.addWidget(file_label)
        select_layout.addWidget(self.file_combobox, 1)

        time_layout = QHBoxLayout()
        time_layout.setSpacing(15)
        time_layout.addWidget(version_label)
        time_layout.addWidget(self.version_combobox, 1)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        self.load_button = QPushButton("加载")
        self.load_button.setIcon(get_icon("加载配置"))
        self.load_button.setStyleSheet(get_button_style_sheet())
        self.compare_button = QPushButton("对比")
        self.compare_button.setIcon(get_icon("对比"))
        self.compare_button.setStyleSheet(get_button_style_sheet())

        for btn in (self.load_button, self.compare_button):
            btn.setMinimumHeight(36)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.compare_button)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        main_layout.addLayout(select_layout)
        main_layout.addLayout(time_layout)
        main_layout.addLayout(button_layout)

        # 信号连接
        self.load_button.clicked.connect(self.on_load)
        self.compare_button.clicked.connect(self.on_compare)
        self.file_combobox.currentIndexChanged.connect(self.update_versions)

        # 初始化一次版本选择
        self.update_versions()

    def update_versions(self):
        self.selected_file = self.file_combobox.currentText()
        if self.selected_file:
            versions = self.file_map[self.selected_file]
            version_labels = [f"{ts}" for ts, _ in versions]
            self.version_combobox.clear()
            self.version_combobox.addItems(version_labels)

    def on_load(self):
        # 获取所选版本
        version_index = self.version_combobox.currentIndex()
        if version_index >= 0:
            selected_version_data = self.file_map[self.selected_file][version_index]
            self.selected_config = selected_version_data[1]  # 获取历史配置
            self.selected_version = self.version_combobox.currentText()  # ✅ 记录版本时间
            self.action = "load"  # 标记为加载动作
            self.accept()  # 关闭对话框，返回已选择的配置

    def on_compare(self):
        # 获取所选版本
        version_index = self.version_combobox.currentIndex()
        if version_index >= 0:
            selected_version_data = self.file_map[self.selected_file][version_index]
            self.selected_config = selected_version_data[1]  # 获取历史配置
            self.selected_version = self.version_combobox.currentText()  # ✅ 记录版本时间
            self.action = "compare"  # 标记为对比动作
            self.accept()  # 关闭对话框，返回已选择的配置
