import copy
import json
import os
import re
from datetime import datetime
from typing import Any

from PyQt5 import sip
from PyQt5.QtCore import (
    Qt,
    QPoint,
    QEvent,
    QPropertyAnimation,
    QAbstractAnimation,
    QRect,
    QTimer,
    QSize,
    QEasingCurve,
    QThreadPool,
)
from PyQt5.QtGui import QColor, QGuiApplication, QIcon
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidgetItem, QWidget, QMenu, QSplitter, QApplication,
    QMessageBox, QScrollArea, QPlainTextEdit, QSizePolicy, QDesktopWidget, QStatusBar, QUndoStack, QUndoCommand,
    QAction, QLabel, QWidgetAction, QCheckBox
)
from PyQt5.QtWidgets import (
    QFileDialog, QInputDialog, QComboBox, QShortcut, QAbstractItemView, QLineEdit
)
from loguru import logger

from application.dialogs.config_setting_dialog import ConfigSettingDialog
from application.dialogs.histogram_range_set_dialog import IntervalPartitionDialog
from application.dialogs.load_history_dialog import LoadHistoryDialog
from application.dialogs.logger_dialog import QTextEditLogger
from application.dialogs.point_selector_dialog import PointSelectorDialog
from application.dialogs.range_input_dialog import RangeInputDialog
from application.dialogs.range_list_dialog import RangeListDialog
from application.dialogs.time_range_dialog import TimeRangeDialog
from application.dialogs.time_selector_dialog import TimeSelectorDialog
from application.dialogs.trend_analysis_dialog import TrendAnalysisDialog
from application.dialogs.update_checker import UpdateChecker
from application.dialogs.version_diff_dialog import VersionDiffDialog
from application.utils.config_handler import (
    load_config,
    save_history,
    save_config,
    HISTORY_PATH,
    PATH_PREFIX,
    FILE_FILTER,
)
from application.utils.data_format_transform import list2str
from application.utils.load_config import ParamConfigLoader
from application.utils.threading_utils import Worker
from application.utils.utils import (
    get_icon,
    get_file_name,
    error_catcher_decorator,
    get_button_style_sheet, get_unique_name,
)
from application.widgets.draggable_tab_bar import DraggableTabBar
from application.widgets.draggable_tree_widget import DraggableTreeWidget
from application.widgets.value_slider import SliderEditor


# 撤销/重做命令类
class TreeEditCommand(QUndoCommand):
    def __init__(self, editor, old_state, description):
        super().__init__(description)
        self.editor = editor
        self.old_state = old_state
        self.new_state = None

    def redo(self):
        if self.new_state:
            # 保存当前树的展开状态
            tree_state = self.editor.capture_tree_state()
            # 保存当前状态
            current_state = self.editor.capture_tree_data()
            # 应用新状态
            self.editor.reload_tree(self.new_state)
            # 恢复树的展开状态
            self.editor.restore_tree_state_only(tree_state)

        return None

    def undo(self):
        # 保存当前树的展开状态
        tree_state = self.editor.capture_tree_state()
        # 保存当前状态作为新状态（首次执行）
        if not self.new_state:
            self.new_state = self.editor.capture_tree_data()
        # 保存当前状态
        current_state = self.editor.capture_tree_data()
        # 恢复旧状态
        self.editor.reload_tree(self.old_state)
        # 恢复树的展开状态
        self.editor.restore_tree_state_only(tree_state)
        return None


class JSONEditor(QWidget):
    def __init__(self):
        super().__init__()
        screen_rect = QDesktopWidget().screenGeometry()
        screen_width, screen_height = screen_rect.width(), screen_rect.height()
        self.window_width = int(screen_width * 0.6)
        self.window_height = int(screen_height * 0.75)
        window_icon = get_icon("logo")
        self.setWindowIcon(QIcon(window_icon.pixmap(QSize(128, 128))))
        self.resize(self.window_width, self.window_height)
        # 窗口大小由外部 showMaximized() 或动态 resize 控制
        self.setAcceptDrops(True)
        self.database_loaded = False  # 当前数据库工具是否完成加载
        self.clipboard_item = None
        self.thread_pool = QThreadPool.globalInstance()
        # 文件管理
        self.open_files = {}  # 原有文件内容存储
        self.orig_files = {}
        self.model_bindings = {}  # 存储每个文件绑定的模型 {filename: model_id}
        self.model_binding_prefix = "当前关联模型参数："
        self.model_binding_structures = {}
        self.file_format = {}
        self.file_states = {}  # 新增：存储每个文件的树状态
        self.current_file = None
        self.untitled_count = 1
        self.active_input = None
        # 动态字体大小
        screen = QGuiApplication.primaryScreen()
        self.scale = int(screen.logicalDotsPerInch() / 96.0)  # 96 DPI 为基准
        base_font = QFont("微软雅黑")
        base_font.setPointSizeF(6 * self.scale)
        self.setFont(base_font)
        # 根据 scale 计算常用间距/圆角
        self.font_size = round(10 * self.scale)

        # 撤销/重做系统
        self.undo_stacks = {}  # 每个文件单独的撤销栈
        self.bind_shortcuts()
        self.setup_log_viwer()
        self.init_ui()
        # 配置参数加载
        self.load_config()

    def load_config(self, config_path="default.yaml"):
        if hasattr(self, "config"):
            del self.config

        self.config = ParamConfigLoader(config_path)
        self.config.params_loaded.connect(self.on_config_loaded)
        self.config.load_async()

    def on_config_loaded(self):
        if hasattr(self, "updater"):
            del self.updater
        if len(self.open_files) == 0:
            self.new_config()
        if self.config.patch_info:
            self.updater = UpdateChecker(self)
            self.updater.check_update()
            self.setWindowTitle(f"{self.config.title} - V{self.updater.current_version}")
        else:
            self.setWindowTitle(
                f"{self.config.title}"
            )

    def init_ui(self):
        # —— 高 DPI 缩放参数 ——
        px6 = int(6 * self.scale)
        px12 = int(12 * self.scale)
        pt11 = round(10 * self.scale)
        pt12 = round(12 * self.scale)

        # 样式表
        self.setStyleSheet(f"""
            QWidget {{ font-family: "Microsoft YaHei"; font-size: {pt11}pt; background-color: #f5f7fa; }}
            QTreeWidget {{ font-size: {pt12}pt; background-color: #ffffff; border: none; }}
            QTreeWidget::item {{ padding: {px6}px; }}
            QPushButton {{
                padding: {px6}px {px12}px;
                border-radius: {px6}px;
                background-color: #0078d7;
                color: white;
                border: none;
            }}
            QPushButton:hover {{ background-color: #3399ff; }}
            QPushButton:pressed {{ background-color: #005a9e; }}
            QLineEdit {{
                padding: {px6}px;
                border: 1px solid #ccc;
                border-radius: {px6}px;
                background: white;
            }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 10px;
                margin: 0px;
            }}

            QScrollBar::handle:vertical {{
                background: #adb5bd;
                border-radius: 5px;
                min-height: 30px;
            }}

            QScrollBar::handle:vertical:hover {{
                background: #868e96;
            }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        # 整体布局（保持原有逻辑，仅缩放数值已用 f-string）
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.tab_bar = DraggableTabBar(self)
        main_layout.addWidget(self.tab_bar)

        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # 左侧工具栏
        self.define_tools()
        self.splitter.addWidget(self.left_panel)

        toggle_wrapper = QWidget()
        toggle_layout = QVBoxLayout(toggle_wrapper)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.addStretch()
        toggle_layout.addStretch()
        self.splitter.addWidget(toggle_wrapper)

        # 右侧主内容（你的树控件等全保留）
        right_splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(right_splitter)
        right_splitter.setSizes([int(0.6 * self.window_height), int(0.4 * self.window_height)])  # 初始高度按需调整

        right_widget = QWidget()
        content_layout = QVBoxLayout(right_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)

        self.tree = DraggableTreeWidget(self)
        self.tree.setHeaderLabels(["参数", "值"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setFont(QFont("微软雅黑", 12))
        self.tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.itemDoubleClicked.connect(self.edit_item_value)
        self.tree.setHeaders()

        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_tree_context_menu)

        content_layout.addWidget(self.tree)
        right_splitter.addWidget(right_widget)

        # 创建右侧日志面板容器
        self.right_log_panel = QWidget()
        self.right_log_panel.setObjectName("RightLogPanel")
        self.right_log_panel.setStyleSheet("""
            #RightLogPanel {
                background: #2c2f36;
                border-left: 1px solid #444;
            }
        """)
        # 动画控制（加入初始化）
        self.log_anim = QPropertyAnimation(self.right_log_panel, b"maximumHeight")
        self.log_anim.setDuration(250)  # 动画时长，单位毫秒
        self.log_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.log_expanded = False  # 初始未展开

        right_splitter.addWidget(self.right_log_panel)
        # 日志面板布局
        log_layout = QVBoxLayout(self.right_log_panel)
        log_layout.addWidget(self.log_viewer)  # 将日志控件嵌入面板
        self.right_log_panel.hide()

        # 初始隐藏日志面板（设置宽度为0）
        self.splitter.setSizes([1, 0, 4])

        # 添加紧凑型状态栏
        self.status_bar = QStatusBar(self)
        self.status_bar.setStyleSheet("""
                    QStatusBar {
                        background-color: #f8f9fa;
                        border-top: 1px solid #e9ecef;
                        color: #6c757d;
                        padding: 1px 8px;
                        font-size: 9pt;
                        min-height: 20px;
                        max-height: 20px;
                    }
                    QStatusBar::item {
                        border: none;
                        margin: 0px;
                    }
                """)
        self.status_bar.setFixedHeight(20)  # 固定高度使其更紧凑

        # 创建模型选择按钮（带下拉箭头）
        self.model_selector_btn = QPushButton("<无关联模型>")  # 允许水平扩展
        self.model_selector_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent; color: #666; padding: 0px 4px; }"
            "QPushButton:hover { color: #1890ff; }"
        )
        self.model_selector_btn.clicked.connect(self.show_model_dropdown)

        # 替换原来的文件信息标签
        self.status_bar.addPermanentWidget(self.model_selector_btn)

        # 添加撤销/重做按钮到状态栏
        undo_btn = QPushButton("撤销")
        undo_btn.setIcon(get_icon("撤销"))
        undo_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent; color: #666; padding: 0px 4px; }"
            "QPushButton:hover { color: #1890ff; }"
        )
        undo_btn.setToolTip(
            "<div style='background-color:#f0f0f0; color:#333333; "
            "border:1px solid #cccccc; padding:4px 8px;'>撤销上一操作 (Ctrl+Z)</div>"
        )
        undo_btn.clicked.connect(self.undo_action)
        self.status_bar.addPermanentWidget(undo_btn)

        redo_btn = QPushButton("重做")
        redo_btn.setIcon(get_icon("重做"))
        redo_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent; color: #666; padding: 0px 4px; }"
            "QPushButton:hover { color: #1890ff; }"
        )
        redo_btn.setToolTip(
            "<div style='background-color:#f0f0f0; color:#333333; "
            "border:1px solid #cccccc; padding:4px 8px;'>重做操作 (Ctrl+Y)</div>"
        )
        redo_btn.clicked.connect(self.redo_action)
        self.status_bar.addPermanentWidget(redo_btn)

        # 在 __init__ 方法中合适的位置添加：
        self.menu_button = QPushButton()
        self.menu_button.setIcon(get_icon("更多"))
        self.menu_button.setToolTip(
            "<div style='background-color:#f0f0f0; color:#333333; "
            "border:1px solid #cccccc; padding:4px 8px;'>更多</div>"
        )
        self.menu_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666;
                font-size: 14pt;
                border: none;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #adb5bd;
                color: white;
            }
            QPushButton:pressed {
                background-color: #e6e6e6;  /* 按下背景变灰 */
                border-radius: 4px;
            }
        """)
        self.menu_button.clicked.connect(self.show_app_menu)

        # 将 menu_button 添加到状态栏右边
        self.status_bar.addPermanentWidget(self.menu_button)

        # 添加状态栏到主布局
        main_layout.addWidget(self.status_bar)

    @error_catcher_decorator
    def show_model_dropdown(self, *args, **kwargs):
        if self.config.api_tools.get("di_flow") is None:
            dialog = QMessageBox(self)
            dialog.setWindowTitle("PostgreSQL 配置缺失")
            dialog.setText("当前未配置 PostgreSQL 数据库连接信息，请先进行配置。")
            dialog.setIcon(QMessageBox.Warning)
            dialog.exec_()
            return

        worker = Worker(fn=self.config.api_tools.get("di_flow").call)
        worker.signals.finished.connect(self.on_di_flow_get)
        worker.signals.error.connect(self.on_di_flow_get)
        self.thread_pool.start(worker)

    def on_di_flow_get(self, model_names):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 10pt;
            }
            QMenu::item:selected {
                background-color: #e6f7ff;
                color: #1890ff;
            }
        """)

        # 创建自定义标题Widget
        title_widget = QLabel("模型列表")
        title_widget.setAlignment(Qt.AlignCenter)  # 设置文字居中
        title_widget.setStyleSheet("font-weight: bold; padding: 4px 0px;")

        # 将标题Widget封装为QWidgetAction
        title_action = QWidgetAction(menu)
        title_action.setDefaultWidget(title_widget)
        menu.addAction(title_action)

        # 获取当前绑定模型
        current_model = self.model_bindings.get(self.current_file)

        # 添加模型项
        for model_name in model_names:
            action = QAction(model_name, menu)
            action.setCheckable(True)
            action.setChecked(model_name == current_model)
            action.triggered.connect(lambda checked, m_id=model_name: self.bind_model(m_id))
            menu.addAction(action)

        # 添加"无关联模型"选项
        no_model_action = QAction("<无关联模型>", menu)
        no_model_action.setCheckable(True)
        no_model_action.setChecked(current_model is None)
        no_model_action.triggered.connect(lambda: self.bind_model(None))
        menu.addAction(no_model_action)

        # 计算弹窗位置（在按钮下方）
        pos = self.model_selector_btn.mapToGlobal(QPoint(0, 0))
        menu_height = menu.sizeHint().height()
        menu_width = menu.sizeHint().width()
        target_pos = QPoint(pos.x() - int(0.5 * menu_width), pos.y() - menu_height)
        menu.exec_(target_pos)

    def bind_model(self, model_id):
        if not self.current_file:
            return
        self.file_states[self.current_file] = self.capture_tree_state()
        # 获取当前模型参数
        current_model = self.model_bindings.get(self.current_file)
        current_data = self.capture_tree_data()

        # 创建撤销命令
        old_state = copy.deepcopy(current_data)

        # 如果已有绑定先移除旧模型
        if current_model:
            prefix = f"{self.model_binding_prefix}{current_model}"
            # 从配置树中移除旧模型参数
            if prefix in current_data:
                del current_data[prefix]

        # 更新绑定关系
        if not model_id or model_id == "<无关联模型>":
            self.model_bindings.pop(self.current_file, None)
            self.model_selector_btn.setText("<无关联模型>")
            self.model_selector_btn.setIcon(QIcon())
            self.undo_stack.push(TreeEditCommand(self, old_state, "取消模型绑定"))
            self.config.remove_binding_model_params()
            self.tree.clear()
            self.load_tree(current_data)
            return
        else:
            self.model_bindings[self.current_file] = model_id
            self.model_selector_btn.setText(model_id)
            self.model_selector_btn.setIcon(get_icon("模型管理"))

        self.model_bindings[self.current_file] = model_id
        worker = Worker(self.config.api_tools.get("di_flow_params").call, self.model_binding_prefix,
                        model_id)
        worker.signals.finished.connect(self.on_model_binded)
        self.thread_pool.start(worker)

    def merge_model_params(self, current_data, model_params, model_name):
        """将模型参数合并到当前配置中"""
        merged = copy.deepcopy(current_data)

        # 查找合适的插入位置（假设插入到根目录）
        model_name = f"{self.model_binding_prefix}{model_name}"
        merged[model_name] = {}

        # 转换模型参数格式
        for param_id, param_info in model_params.items():
            name = param_info.pop("name")
            # 处理组件名称重复
            name = get_unique_name(name, merged[model_name].keys())
            merged[model_name][name] = {}
            for keym, value in param_info.items():
                merged[model_name][name][value.get("param_name")] = value.get("default")

        return merged

    def undo_action(self):
        """执行撤销操作"""
        if self.undo_stack.canUndo():
            self.undo_stack.undo()
            self.show_status_message("已撤销上一操作", "info", 2000)
        else:
            self.show_status_message("没有可撤销的操作", "warning", 2000)

    def redo_action(self):
        """执行重做操作"""
        if self.undo_stack.canRedo():
            self.undo_stack.redo()
            self.show_status_message("已重做操作", "info", 2000)
        else:
            self.show_status_message("没有可重做的操作", "warning", 2000)

    def do_upload(self, name):
        self.auto_save()
        work = Worker(
            self.config.api_tools.get("file_upload").call,
            file_path=os.path.join(
                PATH_PREFIX,
                f"{self.current_file}.{self.file_format.get(self.current_file, 'json')}",
            ),
            dataset_name=name,
            dataset_desc=f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            tree_name="0",
            tree_no="0",
        )
        work.signals.finished.connect(self.update_config)
        self.thread_pool.start(work)

    def update_config(self, file_upload_result):
        file_url = file_upload_result['filePath']
        upload_config_path = self.config.get_upload_name()
        if upload_config_path:
            upload_item = self.get_item_by_path(upload_config_path)
            # 保存当前状态用于撤销
            old_state = self.capture_tree_data()

            # 更新参数值
            upload_item.setText(1, file_url)
            self.config.api_tools.get("di_flow_params_modify").call(
                param_no=self.config.get_model_binding_param_no(upload_config_path),
                param_val=file_url
            )
            # 记录撤销操作
            self.undo_stack.push(TreeEditCommand(self, old_state, f"更新文件地址为: {file_url}"))

            self.show_status_message(f"文件地址已同步: {file_url}", "success")

    def capture_tree_state(self):
        """
        遍历当前 tree，记录所有展开节点的路径和当前选中节点路径
        """
        expanded = set()

        def recurse(item, path):
            key = f"{path}/{item.text(0)}"
            if item.isExpanded():
                expanded.add(key)
            for i in range(item.childCount()):
                recurse(item.child(i), key)

        for i in range(self.tree.topLevelItemCount()):
            recurse(self.tree.topLevelItem(i), "root")

        selected = None
        item = self.tree.currentItem()
        if item:
            path_parts = []
            node = item
            while node:
                path_parts.insert(0, node.text(0))
                node = node.parent()
            selected = '/'.join(path_parts)
        return {'expanded': expanded, 'selected': selected}

    def capture_tree_data(self, tree_root=None):
        """
        将当前 tree 结构及值转换为字典形式，用于保存到 open_files
        """

        def recurse(item):
            node = {}
            # 以节点文本作为 key，若有子节点则递归，否则以文本值作为 leaf
            if item.childCount() == 0:
                return item.text(1)
            else:
                for i in range(item.childCount()):
                    child = item.child(i)
                    node[child.text(0)] = recurse(child)
                return node

        result = {}
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            result[top.text(0)] = recurse(top)
        return result

    def restore_tree_state(self, filename):
        """
        根据保存的状态展开节点并选中节点
        """
        state = self.file_states.get(filename)
        if not state:
            return
        expanded = state['expanded']
        selected = state['selected']

        def recurse(item, path):
            key = f"{path}/{item.text(0)}"
            if key in expanded:
                item.setExpanded(True)
            for i in range(item.childCount()):
                recurse(item.child(i), key)

        for i in range(self.tree.topLevelItemCount()):
            recurse(self.tree.topLevelItem(i), "root")

        if selected:
            parts = selected.split('/')

            def find_item(item, parts):
                if item.text(0) != parts[0]:
                    return None
                if len(parts) == 1:
                    return item
                for i in range(item.childCount()):
                    res = find_item(item.child(i), parts[1:])
                    if res:
                        return res
                return None

            for i in range(self.tree.topLevelItemCount()):
                res = find_item(self.tree.topLevelItem(i), parts)
                if res:
                    self.tree.setCurrentItem(res)
                    break

    def restore_tree_state_only(self, state):
        """
        仅恢复树的展开状态，不改变当前选中项
        用于撤销/重做操作中保持树的展开状态
        """
        if not state:
            return
        expanded = state['expanded']

        def recurse(item, path):
            key = f"{path}/{item.text(0)}"
            if key in expanded:
                item.setExpanded(True)
            for i in range(item.childCount()):
                recurse(item.child(i), key)

        for i in range(self.tree.topLevelItemCount()):
            recurse(self.tree.topLevelItem(i), "root")

    def switch_to_file(self, filename):
        # 如果有当前文件，先保存其数据和状态
        if self.current_file is not None:
            # 1. 保存当前文件配置数据
            self.open_files[self.current_file] = self.capture_tree_data()
            # 2. 保存展开/选中状态
            self.file_states[self.current_file] = self.capture_tree_state()
            if hasattr(self, 'undo_stack'):
                self.undo_stacks[self.current_file] = self.undo_stack

        # 恢复模型绑定状态
        if hasattr(self, 'model_selector_btn'):
            current_model = self.model_bindings.get(filename)
            if current_model:
                self.model_selector_btn.setText(f"{self.model_bindings[filename]}")
                self.model_selector_btn.setIcon(get_icon("模型管理"))
                self.config.add_binding_model_params(self.model_binding_structures.get(filename))
            else:
                self.model_selector_btn.setText("<无关联模型>")
                self.model_selector_btn.setIcon(QIcon())
                self.config.remove_binding_model_params()

        # 切换逻辑
        self.current_file = filename
        self.tree.clear()
        # 从 open_files 中加载配置数据并生成树节点
        self.load_tree(self.open_files[filename])
        # 恢复展开/选中状态
        self.restore_tree_state(filename)

        # 获取目标文件的 undo stack 或新建一个
        self.undo_stack = self.undo_stacks.get(filename, QUndoStack(self))

    def is_same_as_file(self, name):
        # 判断当前配置是否与文件内容一致
        return self.orig_files.get(name, None) == self.open_files.get(name, None)

    def close_file(self, filename):
        # 1. 确认要关闭的确实是打开列表里的
        if filename not in self.open_files:
            return

        # 3. 判断是否是当前激活的 tab
        closing_current = (filename == self.current_file)

        # 4. 如果要关闭的是当前激活的 tab，先记录它在 tabs_layout 中的位置
        if closing_current:
            old_idx = self.tab_bar.index_of(filename)
            # 我们希望跳到左边的那个，如果已经是最左（old_idx==0）就保底选 idx=0
            target_idx = max(0, old_idx - 1)
        else:
            target_idx = None

        # 5. 从数据模型和状态里删
        del self.open_files[filename]
        self.file_states.pop(filename, None)

        # 6. 从 UI 上删按钮
        self.tab_bar.remove_tab_widget(filename)

        # 删除该文件的撤销栈
        self.undo_stacks.pop(filename, None)

        # 7. 如果删完已经没有任何文件，直接 new
        if not self.open_files:
            self.current_file = None
            self.new_config()
            return

        # 8. 如果关闭的是当前文件，用事先算好的 target_idx 跳转
        if closing_current:
            target_name = self.tab_bar.tab_name_at(target_idx)
            self.current_file = None
            self.switch_to_file(target_name)
            self.tab_bar.set_active_tab(target_name)

    def show_status_message(self, message, message_type="info", duration=3000):
        """在状态栏显示美观的临时消息

        参数:
            message: 要显示的消息
            message_type: 消息类型 ("info", "success", "warning", "error")
            duration: 显示时长(毫秒)，0表示永久显示
        """
        # 根据消息类型设置样式
        icon = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "loading": "⏳"
        }.get(message_type, "ℹ️")

        color = {
            "info": "#1890ff",
            "success": "#52c41a",
            "warning": "#faad14",
            "error": "#f5222d",
            "loading": "#1890ff"
        }.get(message_type, "#1890ff")

        # 创建消息标签
        msg_label = QPushButton(f"{icon} {message}")
        msg_label.setStyleSheet(f"""
            QPushButton {{ 
                border: none; 
                background: transparent; 
                color: {color}; 
                padding: 0px 4px;
            }}
        """)

        # 添加到状态栏
        self.status_bar.addWidget(msg_label)

        # 如果设置了显示时长，则定时移除
        if duration > 0:
            QTimer.singleShot(duration, lambda: self.status_bar.removeWidget(msg_label))

        return msg_label

    def new_config(self):
        # 1. 造名、注册模型
        name = f"未命名{self.untitled_count}"
        self.untitled_count += 1
        # 2. 加 UI tab
        name = self.tab_bar.add_tab(name)
        self.config.remove_binding_model_params()
        # 记录打开的配置文件
        self.open_files[name] = copy.deepcopy(self.config.init_params)
        self.orig_files[name] = copy.deepcopy(self.config.init_params)
        self.file_format[name] = "json"
        # 为新文件创建一个新的撤销栈
        self.undo_stacks[name] = QUndoStack(self)

        # 3. 立即切到这个新 tab
        #    这样 current_file、tree、状态 都会被正确赋值
        self.switch_to_file(name)

        # 显示状态消息
        self.show_status_message(f"已创建新配置", "success", 500)

    def define_tools(self):
        QApplication.instance().installEventFilter(self)

        # —— 左侧面板：根据分辨率动态调整工具栏宽度 ——
        self.left_panel = QWidget()
        self.left_panel.setObjectName("ToolPanel")

        # 动态设置工具栏宽度
        tool_panel_width = int(85 * self.scale)  # 工具栏宽度随分辨率调整

        self.left_panel.setMinimumWidth(tool_panel_width)
        self.left_panel.setMaximumWidth(tool_panel_width)

        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 8, 0, 8)
        left_layout.setSpacing(0)
        left_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.left_panel.setStyleSheet("""
            #ToolPanel {
                background: #f5f7fa;
                box-shadow: 1px 0 4px rgba(0, 0, 0, 0.05);
                border: none; /* 确保无任何边框 */
            }
            .QWidget { /* 防止父容器传递边框样式 */
                border: none;
            }
        """)
        self.tools_container = QWidget()
        self.tools_layout = QVBoxLayout(self.tools_container)
        self.tools_layout.setContentsMargins(8, 8, 8, 8)
        self.tools_layout.setSpacing(8)
        self.tools_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # 按钮列表保持不变
        self.tools = [
            # 工具图标名   工具名    工具函数   是否有输入框    输入框函数   输入框默认提示
            ("打开文件", "打开配置", self.import_config, None, None),
            ("save", "保存配置", self.auto_save, None, None),
            ("另存为", "另存为", self.export_config, None, None),
            ("time-history", "历史配置", self.load_history_menu, None, None),
            ("趋势分析", "趋势分析", self.open_trend_analysis, None, None),
            ("search", "配置过滤", self.toggle_search_bar, self.on_search, "支持多个过滤关键字"),
            ("upload", "配置上传", self.toggle_search_bar, self.do_upload, "输入上传文件名称"),
            ("settings", "设置", self.open_setting_dialog, None, None),
            ("日志", "日志", self.toggle_log_viewer, None, None)
        ]

        self.tool_inputs = {}
        for emoji, name, func, input_func, placeholder in self.tools:
            item = QWidget()
            item.setObjectName("ToolItem")
            item.setMinimumHeight(64)
            layout = QHBoxLayout(item)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            layout.setAlignment(Qt.AlignLeft)

            # —— 按钮根据屏幕分辨率动态调整大小 —— #
            btn_size = int(60 * self.scale)  # 按钮大小根据 DPI 调整，避免过大
            font_size = int(8 * self.scale)  # 字体大小也进行适配

            btn = QPushButton()  # 只显示 emoji
            btn.setIcon(get_icon(emoji))  # 设置图标
            btn.setIconSize(QSize(int(0.7 * btn_size), int(0.7 * btn_size)))  # 设置图标大小与按钮一致
            btn.setToolTip(
                "<div style='background-color:#f0f0f0; color:#333333; "
                f"border:1px solid #cccccc; padding:4px 8px;'>{name}</div>"
            )  # 将文字作为 tooltip
            btn.setObjectName("ToolButton")
            btn.setFixedSize(btn_size, btn_size)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                #ToolButton {{
                    background: white;
                    border: 2px solid #dee2e6;
                    border-radius: 6px;
                    color: #495057;
                    font-size: {10 * font_size}pt;
                    text-align: center; /* CSS 样式补充 */
                    padding: 0px; /* 清除默认 padding，防止干扰居中 */
                }}
                #ToolButton:hover {{
                    border-color: #adb5bd;
                    background: #f1f3f5;
                }}
                #ToolButton:pressed {{
                    background: #e9ecef;
                }}
            """)
            input_wrapper = QWidget()
            input_wrapper.setFixedWidth(0)
            input_layout = QHBoxLayout(input_wrapper)
            input_layout.setContentsMargins(0, 0, 0, 0)

            input_field = QLineEdit()
            if placeholder:
                input_field.setPlaceholderText(placeholder)
            input_field.hide()

            anim = QPropertyAnimation(input_wrapper, b"minimumWidth", self)
            anim.setDuration(200)
            anim.setStartValue(0)
            anim.setEndValue(220)

            if input_func:
                btn.clicked.connect(self.create_toggle_handler(input_wrapper, anim, input_field))
                input_field.returnPressed.connect(
                    lambda f=input_func, field=input_field: (
                        f(field.text()), field.clear(), self.hide_input(anim, field)
                    )
                )
                self.tool_inputs[name] = (anim, input_field)
            else:
                btn.clicked.connect(func)

            input_layout.addWidget(input_field)
            layout.addWidget(btn)
            layout.addWidget(input_wrapper)
            self.tools_layout.addWidget(item)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.tools_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_layout.addWidget(self.scroll_area)

        self.panel_anim = QPropertyAnimation(self.left_panel, b"minimumWidth", self)
        self.panel_anim.setDuration(200)

    def create_toggle_handler(self, wrapper, anim, field):
        def handler():
            # —— 如果有别的输入框打开，先隐藏它 —— #
            if self.active_input and self.active_input[0] is not wrapper:
                prev_wrapper, prev_anim, prev_field = self.active_input
                self.hide_input(prev_anim, prev_field)

            # —— 面板宽度动画（保持不变） —— #
            target_w = 300 if (not self.active_input or self.active_input[0] is not wrapper) else 80
            self.panel_anim.stop()
            self.panel_anim.setStartValue(self.left_panel.width())
            self.panel_anim.setEndValue(target_w)
            self.panel_anim.start()

            # —— 切换当前 wrapper —— #
            is_currently_collapsed = not (self.active_input and self.active_input[0] is wrapper)
            if is_currently_collapsed:
                # 展开
                anim.setDirection(QAbstractAnimation.Forward)
                anim.start()
                field.show()
                field.setFocus()
                self.active_input = (wrapper, anim, field)
            else:
                # 收起
                self.hide_input(anim, field)
                self.active_input = None

        return handler

    def hide_input(self, anim, field):
        # 收拢面板
        self.panel_anim.stop()
        self.panel_anim.setStartValue(self.left_panel.width())
        self.panel_anim.setEndValue(85 * self.scale)
        self.panel_anim.start()

        # 隐藏输入框
        anim.setDirection(QAbstractAnimation.Backward)
        anim.start()
        field.hide()

        # 重置
        self.active_input = None

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and self.active_input:
            wrapper, anim, field = self.active_input

            # 把 wrapper 转为全局矩形
            top_left = wrapper.mapToGlobal(QPoint(0, 0))
            rect = QRect(top_left, wrapper.size())

            # 如果点击位置不在 wrapper（包含 field）内，就收起
            if not rect.contains(event.globalPos()):
                self.hide_input(anim, field)
        # 一定要返回父类的过滤结果
        return super().eventFilter(obj, event)

    def toggle_search_bar(self, tool_name):
        """显示/隐藏输入框（保持原功能）"""
        input_field = self.tool_inputs.get(tool_name)
        if input_field:
            input_field.setVisible(not input_field.isVisible())
            if input_field.isVisible():
                input_field.setFocus()

    @error_catcher_decorator
    def edit_item_value(self, item, column):
        if column != 1 or item.data(0, Qt.UserRole):
            return

        full_path = self.get_path_by_item(item)
        param_name = item.text(0)
        current_value = item.text(1)

        # 保存当前状态用于撤销
        old_state = self.capture_tree_data()

        # 使用动画效果突出显示当前编辑的项
        orig_bg = item.background(1)
        item.setBackground(1, QColor('#e6f7ff'))

        param_type = self.config.params_type.get(full_path)

        # 编辑完成后恢复原背景的回调函数
        def restore_background():
            item.setBackground(1, orig_bg)
            self.tree.update()

        if param_type == "time":
            dlg = TimeSelectorDialog(current_value)
            dlg.setWindowTitle(f"选择 {param_name} 时间")
            if dlg.exec_() == QDialog.Accepted:
                item.setText(1, dlg.get_time())
            restore_background()
        elif param_type == "time_range_select":
            # 显示加载提示
            self.show_status_message("正在加载时间范围选择器...")

            # 创建并显示时间范围选择对话框，优化标题和UI
            curve_viewer = TimeRangeDialog(
                self.config.get_tools_by_type("trenddb-fetcher")[0],
                current_text=current_value,
                parent=self
            )
            curve_viewer.setWindowTitle(f"时间范围选择 - {param_name}")

            if curve_viewer.exec_() == QDialog.Accepted:
                # 获取用户选择的时间范围
                new_value = curve_viewer.get_selected_time_ranges()
                item.setText(1, new_value)
                # 高亮显示变化
                if new_value != current_value:
                    item.setForeground(1, QColor('#1890ff'))
                    QTimer.singleShot(2000, lambda: item.setForeground(1, QColor('black')))
            restore_background()
        elif param_type == "dropdown":
            # 初始化编辑器组件
            combo = QComboBox()
            options = self.config.params_options[full_path]
            combo.addItems(options)

            # 设置当前值
            current_index = combo.findText(current_value)
            if current_index >= 0:
                combo.setCurrentIndex(current_index)

            # 连接事件：当选项改变时更新值并高亮
            def on_combo_activated():
                new_value = combo.currentText()
                if new_value != current_value:
                    item.setText(1, new_value)
                    # 如果属于关联模型配置，则同步修改数据库内容
                    if re.search(self.model_binding_prefix, full_path):
                        param_no = self.config.get_model_binding_param_no(full_path)
                        option_value = self.option2val.get(param_no).get(new_value)
                        self.config.api_tools.get("di_flow_params_modify").call(
                            param_no=param_no,
                            param_val=option_value
                        )
                    item.setForeground(1, QColor("#1890ff"))
                    QTimer.singleShot(
                        2000, lambda: item.setForeground(1, QColor("black"))
                    )
                # 移除控件
                self.tree.removeItemWidget(item, column)
                # 恢复背景
                restore_background()

            combo.activated.connect(on_combo_activated)

            # 显示下拉框编辑器
            self.tree.setItemWidget(item, column, combo)
        elif param_type == "partition":
            # 获取同级测点名列表
            parent = item.parent()
            select_point = None

            # 寻找测点名参数
            for i in range(parent.childCount()):
                if parent.child(i).text(0) == "测点名":
                    select_point = parent.child(i).text(1).split("\n")[0]
                    break

            if select_point:
                # 显示加载提示
                self.show_status_message(f"正在为测点 {select_point} 加载数据...")

                # 弹出划分对话框
                dlg = IntervalPartitionDialog(
                    dfs=self.config.get_tools_by_type("trenddb-fetcher"),
                    point_name=select_point,
                    current_text=current_value,
                    type="partition",
                    parent=self
                )
                dlg.setWindowTitle(f"区间划分 - {param_name} - {select_point}")

                # 用户需要先在主界面勾选测点，再使用对话框中的时间范围和分箱宽度获取数据
                if dlg.exec_() == QDialog.Accepted:
                    intervals = dlg.get_intervals()
                    # 格式化区间字符串，增加易读性
                    text = list2str(intervals)
                    item.setText(1, text)
                    # 高亮显示变化
                    if text != current_value:
                        item.setForeground(1, QColor("#1890ff"))
                        QTimer.singleShot(
                            2000, lambda: item.setForeground(1, QColor("black"))
                        )
                restore_background()
            else:
                # 如果没有找到测点，使用纯手动编辑模式
                dlg = RangeListDialog(current_value)
                dlg.setWindowTitle(f"区间列表编辑 - {param_name}")
                if dlg.exec_() == QDialog.Accepted:
                    new_value = dlg.get_ranges()
                    if new_value != current_value:
                        item.setText(1, new_value)
                        # 高亮新值
                        item.setForeground(1, QColor('#1890ff'))
                        QTimer.singleShot(2000, lambda: item.setForeground(1, QColor('black')))
            restore_background()
        elif param_type == "range":
            # 获取同级测点名列表
            parent = item.parent()
            select_point = None

            # 查找相关测点
            for i in range(parent.childCount()):
                if parent.child(i).text(0) == "测点名":
                    select_point = parent.child(i).text(1).split("\n")[0]
                    break

            if select_point:
                # 显示加载状态
                self.show_status_message(f"正在为测点 {select_point} 加载数据范围...")

                # 弹出划分对话框
                dlg = IntervalPartitionDialog(
                    dfs=self.config.get_tools_by_type("trenddb-fetcher"),
                    point_name=select_point,
                    current_text=current_value,
                    type="range",
                    parent=self
                )
                dlg.setWindowTitle(f"数值范围选择 - {param_name} - {select_point}")

                # 用户需要先在主界面勾选测点，再使用对话框中的时间范围和分箱宽度获取数据
                if dlg.exec_() == QDialog.Accepted:
                    intervals = dlg.get_intervals()
                    if intervals:
                        # 格式化区间字符串为整体范围
                        text = list2str(intervals)
                        if text != current_value:
                            item.setText(1, text)
                            # 高亮新值
                            item.setForeground(1, QColor("#1890ff"))
                            QTimer.singleShot(
                                2000, lambda: item.setForeground(1, QColor("black"))
                            )
            else:
                # 如果没有找到测点，使用纯手动编辑模式
                dlg = RangeInputDialog(current_value)
                dlg.setWindowTitle(f"范围输入 - {param_name}")
                if dlg.exec_() == QDialog.Accepted:
                    if dlg.result != current_value:
                        item.setText(1, dlg.result)
                        # 高亮显示新值
                        item.setForeground(1, QColor('#1890ff'))
                        QTimer.singleShot(2000, lambda: item.setForeground(1, QColor('black')))
            restore_background()
        elif param_type == "fetch":
            # 显示加载状态
            self.show_status_message("正在加载测点选择器...")

            # 获取当前编辑路径的测点获取工具
            fetchers = self.config.get_tools_by_path(full_path)

            # 创建并显示测点选择对话框
            dlg = PointSelectorDialog(
                fetchers=fetchers,
                data_fetcher=self.config.get_tools_by_type("trenddb-fetcher")[0],
                current_value=current_value,
                parent=self
            )
            dlg.setWindowTitle(f"测点选择 - {param_name}")

            if dlg.exec_() == QDialog.Accepted:
                selected_point = dlg.selected_point
                selected_description = dlg.selected_point_description

                # 确保 selected_description 是字符串类型
                selected_description = str(selected_description)

                # 组合显示值
                new_value = f"{selected_point}\n{selected_description}"

                if new_value != current_value:
                    item.setText(1, new_value)
                    # 高亮新值
                    item.setForeground(1, QColor("#1890ff"))
                    QTimer.singleShot(
                        2000, lambda: item.setForeground(1, QColor("black"))
                    )
            restore_background()
            # —— 其他类型分支 —— #
        elif param_type == "slider":
            # 从文本获取初始值
            try:
                init = int(item.text(1))
            except ValueError:
                init = 0

            item.setText(1, "")
            # 获取滑块条上下限，通过options配置
            bound = self.config.params_options.get(full_path, [0, 100, 1])

            # 高级滑块编辑器配置
            decimal_num = 1 if len(bound) < 3 else int(bound[2])
            editor = SliderEditor(
                minimum=int(bound[0]),
                maximum=int(bound[1]),
                initial=init if len(current_value) == 0 else round(float(current_value), decimal_num),
                decimal_point=decimal_num,
            )

            # 值变化回调
            def on_confirm(value):
                it = item  # 捕获外部的item变量
                it.setText(1, str(value))
                # 高亮显示修改后的值
                it.setForeground(1, QColor('#1890ff'))

                # 使用安全的引用方式处理延迟操作
                def safe_reset_color():
                    try:
                        if it and not sip.isdeleted(it):
                            it.setForeground(1, QColor('black'))
                            # 移除滑块控件，实现自动消失
                            self.tree.removeItemWidget(it, column)
                    except (RuntimeError, TypeError, ReferenceError):
                        pass

                QTimer.singleShot(100, safe_reset_color)

            editor.confirmStateChanged.connect(on_confirm)
            self.tree.setItemWidget(item, column, editor)
        else:
            # 创建更美观的输入对话框
            dialog = QInputDialog(self)
            dialog.setInputMode(QInputDialog.TextInput)
            dialog.setWindowTitle(f"编辑 {param_name}")
            dialog.setLabelText(f"请输入 {param_name} 的新值:")
            dialog.setTextValue(current_value)
            dialog.setStyleSheet("""
                QInputDialog {
                    background-color: #f5f7fa;
                }
                QLabel {
                    font-size: 12pt;
                    color: #222;
                    margin-bottom: 8px;
                }
                QLineEdit {
                    padding: 8px;
                    border: 1px solid #1890ff;
                    border-radius: 4px;
                    font-size: 11pt;
                }
            """ + get_button_style_sheet())
            dialog.resize(350, dialog.height())

            if dialog.exec_() == QDialog.Accepted:
                text = dialog.textValue()
                if text != current_value:
                    item.setText(1, text)
                    # 如果属于关联模型配置，则同步修改数据库内容
                    if re.search(self.model_binding_prefix, full_path):
                        self.config.api_tools.get("di_flow_params_modify").call(
                            param_no=self.config.get_model_binding_param_no(full_path),
                            param_val=text
                        )
                    # 高亮新值
                    item.setForeground(1, QColor("#1890ff"))
                    QTimer.singleShot(
                        2000, lambda: item.setForeground(1, QColor("black"))
                    )
            restore_background()

        # 记录撤销操作
        self.undo_stack.push(TreeEditCommand(self, old_state, f"编辑 {param_name}"))

    # ================= 增强的导入/导出方法 =================
    def import_config(self):
        """导入配置文件，支持覆盖/保留/跳过"""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", PATH_PREFIX, "配置文件 (*.json *.yaml *.yml *.ini)"
        )
        if not path:
            return

        filename = get_file_name(path)

        # 文件名冲突处理
        if filename in self.open_files:
            box = QMessageBox(self)
            box.setWindowTitle("文件已存在")
            box.setText(f"文件“{filename}”已经打开，是否覆盖当前配置？")
            cover_btn = box.addButton("覆盖", QMessageBox.AcceptRole)
            cover_btn.setIcon(get_icon("覆盖"))
            cover_btn.setStyleSheet(get_button_style_sheet())

            keep_btn = box.addButton("保留", QMessageBox.YesRole)
            keep_btn.setIcon(get_icon("重命名"))
            keep_btn.setStyleSheet(get_button_style_sheet())

            skip_btn = box.addButton("跳过", QMessageBox.RejectRole)
            skip_btn.setIcon(get_icon("跳过步骤"))
            skip_btn.setStyleSheet(get_button_style_sheet())
            box.setDefaultButton(cover_btn)
            box.exec_()

            clicked = box.clickedButton()

            if clicked == skip_btn:
                return
            elif clicked == keep_btn:
                # 自动重命名
                base, ext = os.path.splitext(filename)
                i = 1
                new_filename = f"{base}_{i}{ext}"
                while new_filename in self.open_files:
                    i += 1
                    new_filename = f"{base}_{i}{ext}"
                filename = new_filename
            elif clicked == cover_btn:
                config = load_config(path)
                self.open_files[filename] = config
                self.orig_files[filename] = config
                if self.current_file == filename:
                    self.tree.clear()
                    self.load_tree(config)
                else:
                    self.switch_to_file(filename)
                return

        # 正常添加新文件
        config = load_config(path)
        self.open_files[filename] = config
        self.orig_files[filename] = config
        self.file_format[filename] = path.split(".")[-1]
        self.tab_bar.add_tab(filename)
        self.switch_to_file(filename)
        self.show_status_message(f"文件加载成功!", "success")

    def auto_save(self):
        if not self.current_file:
            return

        # 获取数据并保存
        data = self.tree_to_dict()
        file_name = f"{self.current_file}.{self.file_format.get(self.current_file, 'json')}"
        save_config(os.path.join(PATH_PREFIX, file_name), data)
        save_history(os.path.join(PATH_PREFIX, file_name), data)
        self.orig_files[self.current_file] = self.open_files[self.current_file]
        # 显示保存成功消息
        save_time = datetime.now().strftime("%H:%M:%S")
        self.show_status_message(f"文件已保存! ({save_time})", "success", 3000)
        logger.info(f"{self.current_file} 文件自动保存成功!")

    def rename_file(self, old_name, new_name):
        # 更新 open_files
        del self.file_states[old_name]
        del self.undo_stacks[old_name]
        del self.open_files[old_name]
        if self.current_file is not None:
            # 1. 保存当前文件配置数据
            self.open_files[new_name] = self.capture_tree_data()
            # 2. 保存展开/选中状态
            self.file_states[new_name] = self.capture_tree_state()
            self.orig_files[new_name] = self.orig_files.pop(old_name)
            self.file_format[new_name] = self.file_format.pop(old_name)
            if hasattr(self, 'undo_stack'):
                self.undo_stacks[new_name] = self.undo_stack

        self.current_file = new_name
        if old_name in self.model_bindings:
            self.model_bindings[new_name] = self.model_bindings.pop(old_name)
            self.model_binding_structures[new_name] = self.model_binding_structures.pop(old_name)
        self.show_status_message(f"文件已重命名!", "success")

    def export_config(self):
        if not self.current_file:
            return
        data = self.tree_to_dict()
        path, _ = QFileDialog.getSaveFileName(
            self, "保存配置", os.path.join(PATH_PREFIX, self.current_file), FILE_FILTER)
        if not path:
            return
        save_config(path, data)
        save_history(path, data)
        save_time = datetime.now().strftime("%H:%M:%S")
        self.show_status_message(f"文件已保存! ({save_time})!", "success")
        self.orig_files[".".join(os.path.basename(path).split(".")[:-1])] = self.open_files[self.current_file]
        self.tab_bar.rename_tab(self.current_file, ".".join(os.path.basename(path).split(".")[:-1]))

    def bind_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+S"), self, self.export_config)
        QShortcut(QKeySequence("Ctrl+A"), self, self.add_sub_param)
        QShortcut(QKeySequence("Delete"), self, self.remove_param)
        QShortcut(QKeySequence("Ctrl+X"), self, self.cut_item)
        QShortcut(QKeySequence("Tab"), self, self.load_history_menu)
        QShortcut(QKeySequence("Ctrl+C"), self, self.copy_item)
        QShortcut(QKeySequence("Ctrl+V"), self, self.paste_item)

        # 添加撤销/重做快捷键
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo_action)
        QShortcut(QKeySequence("Ctrl+Y"), self, self.redo_action)

    def on_tree_context_menu(self, pos: QPoint):
        # 获取当前项
        item = self.tree.itemAt(pos)

        # 创建上下文菜单
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #ccc;
                border-radius: 6px;
                font-size: 11pt;
                padding: 4px 0px;
            }
            QMenu::item {
                padding: 8px 30px 8px 20px;
                color: #333333;
            }
            QMenu::item:selected {
                background-color: #1890ff;
                color: white;
            }
            QMenu::icon {
                margin-left: 10px;
            }
            QMenu::separator {
                height: 1px;
                background: #e0e0e0;
                margin: 5px 10px;
            }
            QMenu::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        # 创建操作并添加图标
        style = self.style()

        # 创建一级菜单项
        menu.addAction("添加子参数", self.add_sub_param)
        menu.addAction("新增参数", self.add_param)

        menu.addSeparator()

        if item:
            # 编辑操作作为一级菜单项
            menu.addAction("编辑值", lambda: self.edit_item_value(item, 1))

            # 剪贴板操作
            menu.addAction("复制", lambda: self.copy_item(item))
            menu.addAction("剪切", lambda: self.cut_item())

            # 粘贴操作 - 仅当剪贴板有内容时才启用
            paste_action = menu.addAction("粘贴", lambda: self.paste_item(item))
            paste_action.setEnabled(self.clipboard_item is not None)

            # 删除操作
            menu.addAction("删除参数", self.remove_param)

        menu.addSeparator()

        # 视图操作作为一级菜单项
        menu.addAction("展开全部", self.tree.expandAll)
        menu.addAction("折叠全部", self.tree.collapseAll)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def copy_item(self, item=None):
        if item is None:
            item = self.tree.currentItem()
        if item:
            self.clipboard_item = self.clone_item(item)
        self.show_status_message("已复制配置!", "success")

    def cut_item(self):
        item = self.tree.currentItem()
        if item:
            # 保存当前状态用于撤销
            old_state = self.capture_tree_data()
            param_name = item.text(0)

            self.copy_item(item)  # 复制当前项及其子项

            # 删除操作，但不再调用remove_param()以避免重复添加撤销命令
            parent = item.parent()
            if parent:
                parent.removeChild(item)
            else:
                index = self.tree.indexOfTopLevelItem(item)
                self.tree.takeTopLevelItem(index)

            # 记录撤销操作
            self.undo_stack.push(TreeEditCommand(self, old_state, f"剪切参数 {param_name}"))
            self.show_status_message("已剪切配置!", "success")

    def paste_item(self, parent_item=None):
        if self.clipboard_item:
            # 保存当前状态用于撤销
            old_state = self.capture_tree_data()
            item_name = self.clipboard_item.text(0)

            if parent_item is None:
                parent_item = self.tree.currentItem()
            if parent_item:
                new_item = self.clone_item(self.clipboard_item)
                parent_item.addChild(new_item)
                parent_item.setExpanded(True)
                target_name = parent_item.text(0)
            else:
                new_item = self.clone_item(self.clipboard_item)
                self.tree.addTopLevelItem(new_item)
                target_name = "根目录"

            # 记录撤销操作
            self.undo_stack.push(TreeEditCommand(self, old_state, f"粘贴 {item_name} 到 {target_name}"))
            self.show_status_message("已黏贴配置！", "success")

    def clone_item(self, item):
        new_item = QTreeWidgetItem([item.text(0), item.text(1)])
        for i in range(item.childCount()):
            child = item.child(i)
            new_child = self.clone_item(child)
            new_item.addChild(new_child)
        return new_item

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def gather_tags(self,
                    data: dict = None,
                    tag_name: str = "测点名",
                    type: Any = "",
                    with_type: bool = False) -> list:
        """
        将配置文件中的配置参数名称进行提取
        :param data: 待提取配置文件
        :param tag_name: 标签名，默认为测点名
        :param type: 标签类型，比如：控制参数、目标参数。。。
        :param with_type: 提取结果是否带标签信息
        :return:
        """
        data = self.tree_to_dict() if data is None else data

        tags = []
        for k, v in data.items():
            if len(type) > 0 and k not in type: continue
            if isinstance(v, dict):
                new_tags = self.gather_tags(v)
                tags.extend(
                    [f"{k}:{tag}" for tag in new_tags]
                    if with_type
                    else new_tags
                )
            elif k == tag_name and len(v) > 0:
                tags.append(v)
                return tags

        return tags

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.split(".")[-1] not in ["json", "yaml", "yml", "ini"]:
                continue

            filename = get_file_name(path)

            if filename in self.open_files:
                box = QMessageBox(self)
                box.setWindowTitle("文件已存在")
                box.setText(f"文件“{filename}”已经打开，是否覆盖当前配置？")
                cover_btn = box.addButton("覆盖", QMessageBox.AcceptRole)
                keep_btn = box.addButton("保留", QMessageBox.YesRole)
                skip_btn = box.addButton("跳过", QMessageBox.RejectRole)
                box.setDefaultButton(cover_btn)
                box.exec_()

                clicked = box.clickedButton()

                if clicked == skip_btn:
                    return
                elif clicked == keep_btn:
                    # 自动重命名
                    base, ext = os.path.splitext(filename)
                    i = 1
                    new_filename = f"{base}_{i}{ext}"
                    while new_filename in self.open_files:
                        i += 1
                        new_filename = f"{base}_{i}{ext}"
                    filename = new_filename
                elif clicked == cover_btn:
                    config = load_config(path)
                    self.open_files[filename] = config
                    self.orig_files[filename] = config
                    if self.current_file == filename:
                        self.tree.clear()
                        self.load_tree(config)
                    else:
                        self.switch_to_file(filename)
                    return

            # 没有重复或选择保留 -> 正常添加
            config = load_config(path)
            self.open_files[filename] = config
            self.orig_files[filename] = config
            self.file_format[filename] = path.split(".")[-1]
            self.tab_bar.add_tab(filename)
            self.switch_to_file(filename)

    def reload_tree(self, data):
        self.tree.clear()
        self.load_tree(data)

    def get_path_by_item(self, item):
        parts = []
        while item:
            if not re.search(r' [参数]*[0-9]+', item.text(0)): parts.insert(0, item.text(0))
            item = item.parent()

        return "/".join(parts)

    def get_item_by_path(self, path):
        """
        根据路径字符串查找对应的 QTreeWidgetItem
        :param path: 路径字符串，如 "根节点/子节点/目标节点"
        :return: 匹配的 QTreeWidgetItem 或 None
        """
        if not path or not self.tree:
            return None

        # 分割路径
        target_parts = path.split('/')

        # 从顶层节点开始查找
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            result = self._find_child_by_path(top_item, target_parts)
            if result:
                return result

        return None

    def _find_child_by_path(self, item, parts):
        """
        递归查找子节点
        :param item: 当前检查的节点
        :param parts: 剩余路径部分
        :return: 匹配的 QTreeWidgetItem 或 None
        """
        if not parts:
            return item  # 路径已匹配完成

        current_part = parts[0]

        # 检查当前节点是否匹配路径段（同时考虑正则排除逻辑）
        if item.text(0) == current_part:
            if len(parts) == 1:
                return item  # 最后一个路径段匹配成功
            else:
                # 继续查找子节点
                for i in range(item.childCount()):
                    child = item.child(i)
                    match = self._find_child_by_path(child, parts[1:])
                    if match:
                        return match
        return None

    def lock_item(self, key, parent, item):
        full_path = self.get_path_by_item(item)
        if self.config.params_type.get(full_path) in ["group", "subgroup"]:
            self.mark_item_locked(item)
        if parent and re.search(r' [参数]*[0-9]+', key):
            parent_path = self.get_path_by_item(parent)
            if self.config.params_type.get(parent_path) == "subgroup":
                self.mark_item_locked(item)

    def load_tree(self, data, parent=None, path_prefix="", bind_model=True):
        # 加载配置时如果有对应prefix的配置，自动关联到对应模型
        for key in data:
            if re.search(f"{self.model_binding_prefix}", key):
                break

        if bind_model and re.search(f"{self.model_binding_prefix}", key):
            model_name = re.findall(rf"{self.model_binding_prefix}(.+)", key)[0]
            if model_name != self.model_bindings.get(self.current_file):
                self.model_bindings[self.current_file] = model_name
                worker = Worker(self.config.api_tools.get("di_flow_params").call, self.model_binding_prefix,
                                model_name)
                worker.signals.finished.connect(lambda result: self.on_model_binded(result, data))
                self.thread_pool.start(worker)
                return
            else:
                self.config.add_binding_model_params(self.model_binding_structures[self.current_file])
                self.model_selector_btn.setText(self.model_bindings.get(self.current_file))
                self.model_selector_btn.setIcon(get_icon("模型管理"))

        for key, value in data.items():
            full_path = f"{path_prefix}/{key}" if path_prefix and not re.search(r' [参数]*[0-9]+', key) else key
            if isinstance(value, list):
                item = QTreeWidgetItem([key, list2str(value)])

                if parent:
                    parent.addChild(item)
                else:
                    self.tree.addTopLevelItem(item)

            elif isinstance(value, dict):
                item = QTreeWidgetItem([key, ""])
                if parent:
                    parent.addChild(item)
                else:
                    self.tree.addTopLevelItem(item)

                self.lock_item(key, parent, item)
                if re.search(r' [参数]*[0-9]+', full_path):
                    self.load_tree(value, item, path_prefix=path_prefix, bind_model=False)
                else:
                    self.load_tree(value, item, path_prefix=full_path, bind_model=False)
            else:
                param_type = self.config.params_type.get(full_path)
                if param_type == "checkbox":
                    old_state = self.capture_tree_data()
                    item = QTreeWidgetItem([key, str(value)])
                    cb = QCheckBox()
                    cb.setStyleSheet("""
                        QCheckBox {
                            background-color: transparent;
                            color: #333;
                            spacing: 8px;
                            font-size: 18px;
                        }
                        QCheckBox::indicator {
                            width: 18px;
                            height: 18px;
                            border: 2px solid #1890ff;
                            border-radius: 4px;
                            background-color: white;
                            text-align: center;
                        }
                        QCheckBox::indicator:checked {
                            background-color: #1890ff;
                            border: 2px solid #1890ff;
                            color: white;
                        }
                        QCheckBox::indicator:checked::text {
                            content: "✔";
                        }
                    """)
                    options = self.config.params_options[full_path]
                    cb.setChecked(value == options[1])
                    cb.setText(options[1] if value == options[1] else options[0])
                    item.setData(1, Qt.UserRole, cb)  # 存储控件引用
                    if parent:
                        parent.addChild(item)
                    else:
                        self.tree.addTopLevelItem(item)
                    self.tree.setItemWidget(item, 1, cb)

                    # 连接事件更新值
                    def on_check(box, it, path, number):
                        new_val = options[1] if box.isChecked() else options[0]
                        it.setText(1, new_val)
                        # 如果属于关联模型配置，则同步修改数据库内容
                        if re.search(self.model_binding_prefix, path):
                            param_no = self.config.get_model_binding_param_no(path)
                            option_value = self.option2val.get(param_no).get(new_val)
                            self.config.api_tools.get("di_flow_params_modify").call(
                                param_no=param_no,
                                param_val=option_value
                            )
                        box.setText(options[1] if new_val == options[1] else options[0])
                        # 高亮变化
                        it.setForeground(1, QColor("#1890ff"))
                        QTimer.singleShot(2000, lambda: it.setForeground(1, QColor("black")))

                    cb.stateChanged.connect(lambda number, b=cb, it=item, path=full_path: on_check(b, it, path, number))
                else:
                    item = QTreeWidgetItem([key, str(value)])
                    if parent:
                        parent.addChild(item)
                    else:
                        self.tree.addTopLevelItem(item)
                    self.lock_item(key, parent, item)

    def on_model_binded(self, result, current_data=None):
        self.config.remove_binding_model_params()
        current_data = self.capture_tree_data() if current_data is None else current_data
        model_params, param_structure, self.option2val = result
        self.model_binding_structures[self.current_file] = param_structure
        self.config.add_binding_model_params(param_structure)
        self.model_selector_btn.setText(self.model_bindings.get(self.current_file))
        self.model_selector_btn.setIcon(get_icon("模型管理"))

        # 去除之前关联的模型
        current_data = {
            key: value for key, value in current_data.items()
            if not re.search(f"{self.model_binding_prefix}", key)
        }
        merged_data = self.merge_model_params(current_data, model_params, self.model_bindings.get(self.current_file))
        self.open_files[self.current_file] = merged_data
        # 更新树
        self.tree.clear()
        self.load_tree(merged_data, bind_model=False)
        self.restore_tree_state(self.current_file)
        # 更新撤销栈
        self.undo_stack.push(
            TreeEditCommand(self, current_data, f"绑定模型: {self.model_bindings.get(self.current_file)}"))

        self.show_status_message(f"已绑定模型: {self.model_bindings.get(self.current_file)}", "success")

    def add_param(self):
        item = self.tree.currentItem()
        name, ok = QInputDialog.getText(self, "参数名称", "请输入参数名称:")
        if ok and name:
            value, ok = QInputDialog.getText(self, "参数值", "请输入参数值:")
            if ok:
                # 保存当前状态用于撤销
                old_state = self.capture_tree_data()

                new_item = QTreeWidgetItem([name, value])
                if item:
                    item.addChild(new_item)
                else:
                    self.tree.addTopLevelItem(new_item)

                # 记录撤销操作
                self.undo_stack.push(TreeEditCommand(self, old_state, f"添加参数 {name}"))

    def add_sub_param(self, item=None, tag_name=None):
        """添加预制子参数"""
        item = self.tree.currentItem() if item is None else item
        if item:
            # 保存当前状态用于撤销
            old_state = self.capture_tree_data()

            full_path = self.get_path_by_item(item)
            parent_name = item.text(0)
            sub_params_dict = {parent_name: self.config.subchildren_default[full_path]} \
                if self.config.params_type[full_path] == "subgroup" else {}

            sub_params = sub_params_dict.get(parent_name, {})
            sub_param_item = QTreeWidgetItem([f"{parent_name} {item.childCount() + 1}", ""])
            self.mark_item_locked(sub_param_item)  # 为预制参数容器锁定
            item.addChild(sub_param_item)

            for sub_param, value in sub_params.items():
                sub_param_path = f"{full_path}/{sub_param}"
                if self.config.params_type.get(sub_param_path) == "range" and isinstance(value, list):
                    sub_item = QTreeWidgetItem([sub_param, ""])
                elif self.config.params_type.get(sub_param_path) == "fetch" and tag_name is not None:
                    sub_item = QTreeWidgetItem([sub_param, tag_name])
                elif self.config.params_type.get(sub_param_path) == "group":
                    sub_item = QTreeWidgetItem([sub_param, ""])
                    self.lock_item(sub_param, sub_item, sub_item)
                    for param, v in value.items():
                        sub_item.addChild(QTreeWidgetItem([param, v]))
                else:
                    sub_item = QTreeWidgetItem([sub_param, str(value)])
                sub_param_item.addChild(sub_item)
                self.lock_item(sub_param, sub_item, sub_item)

            # 记录撤销操作
            self.undo_stack.push(TreeEditCommand(self, old_state, f"添加子参数到 {parent_name}"))

    def remove_param(self):
        item = self.tree.currentItem()
        if item:
            # 保存当前状态用于撤销
            old_state = self.capture_tree_data()
            param_name = item.text(0)

            parent = item.parent()
            if parent:
                parent.removeChild(item)
            else:
                index = self.tree.indexOfTopLevelItem(item)
                self.tree.takeTopLevelItem(index)

            # 记录撤销操作
            self.undo_stack.push(TreeEditCommand(self, old_state, f"删除参数 {param_name}"))
            self.show_status_message("已删除配置", "success")

    def load_history_menu(self):
        if not os.path.exists(HISTORY_PATH):
            return

        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            history = json.load(f)

        file_map = {}
        for record in history:
            file, timestamp, config = record
            if file not in file_map:
                file_map[file] = []
            file_map[file].append((timestamp, config))

        filenames = list(file_map.keys())

        for versions in file_map.values():
            versions.sort(key=lambda x: datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S"), reverse=True)

        # 新的加载对话框
        load_history_dialog = LoadHistoryDialog(file_map, filenames, self)

        if load_history_dialog.exec_() == QDialog.Accepted:
            selected_file = load_history_dialog.selected_file
            selected_version = load_history_dialog.selected_version
            selected_config = load_history_dialog.selected_config

            current_config = self.get_current_config()

            if load_history_dialog.action == "load":
                # 新增逻辑：作为新配置打开
                history_filename = f"[历史]{os.path.basename(selected_file)}-{selected_version}"
                history_filename = self.tab_bar.add_tab(history_filename)
                self.open_files[history_filename] = selected_config
                self.switch_to_file(history_filename)

            elif load_history_dialog.action == "compare":
                # 对比功能保持不变
                compare_dialog = VersionDiffDialog(
                    selected_config, current_config,
                    lambda config: self.reload_tree(config),
                    selected_file, selected_version
                )
                compare_dialog.exec_()

    def get_current_config(self):
        def extract_item(item):
            data = {}
            for i in range(item.childCount()):
                child = item.child(i)
                key = child.text(0)
                value = child.text(1)
                if child.childCount() > 0:
                    data[key] = extract_item(child)
                else:
                    data[key] = value
            return data

        config = {}
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            key = top_item.text(0)
            value = top_item.text(1)
            if top_item.childCount() > 0:
                config[key] = extract_item(top_item)
            else:
                config[key] = value
        return config

    def tree_to_dict(self, item=None):
        def parse_item(itm):
            children = [parse_item(itm.child(i)) for i in range(itm.childCount())]
            key = itm.text(0)
            val = itm.text(1)
            full_path = self.get_path_by_item(itm)
            param_type = self.config.params_type.get(full_path)

            if children:
                if all(c[0] == "" for c in children):
                    return key, [c[1] for c in children]
                else:
                    child_dict = {}
                    key_counts = {}
                    for k, v in children:
                        if k in child_dict:
                            key_counts[k] = key_counts.get(k, 1) + 1
                            new_key = f"{k}_{key_counts[k]}"
                        else:
                            key_counts[k] = 1
                            new_key = k
                        child_dict[new_key] = v
                    return key, child_dict
            else:
                if param_type == "range":
                    return RangeInputDialog.save(key, val)
                elif param_type == "partition":
                    return RangeListDialog.save(key, val)
                elif param_type == "time_range_select":
                    return TimeRangeDialog.save(key, val)

                return key, val

        result = {}
        key_counts = {}
        for i in range(self.tree.topLevelItemCount()):
            key, val = parse_item(self.tree.topLevelItem(i))
            if key in result:
                key_counts[key] = key_counts.get(key, 1) + 1
                new_key = f"{key}_{key_counts[key]}"
            else:
                key_counts[key] = 1
                new_key = key
            result[new_key] = val
        return result

    def mark_item_locked(self, item):
        """标记项目为锁定状态，更显眼的视觉提示"""
        # 仅禁用编辑，但保留可选中以显示高亮
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)

        # 参数组标题使用蓝灰色背景
        item.setForeground(0, QColor("#444444"))
        item.setForeground(1, QColor("#444444"))
        item.setBackground(0, QColor("#e6f7ff"))
        item.setBackground(1, QColor("#e6f7ff"))

        # 设置字体加粗
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)

        # 标记为锁定
        item.setData(0, Qt.UserRole, True)

    def on_search(self, text):
        # 先展开所有节点
        self.expand_all_items(self.tree.invisibleRootItem())

        # 如果搜索框为空，就直接显示所有节点
        if not text.strip():
            self.show_all_items(self.tree.invisibleRootItem())
            return

        # 否则按逗号分隔成多个关键字
        text = text.replace("；", ";").replace(",", ";").replace("，", ";").replace(" ", ";").replace("　", ";")
        filters = [
            kw.strip().lower() for kw in text.split(';') if kw.strip()
        ]

        # 递归更新可见性
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            self.update_item_visibility(item, filters)

    def show_all_items(self, parent_item):
        """递归把所有项都设为可见"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child.setHidden(False)
            self.show_all_items(child)

    def update_item_visibility(self, item, filters):
        """更新单项可见性（任意关键字命中或有子项命中就显示）"""
        match_in_children = False
        for i in range(item.childCount()):
            child = item.child(i)
            if self.update_item_visibility(child, filters):
                match_in_children = True

        match_in_self = self.search_item_in_all_columns(item, filters)
        item.setHidden(not (match_in_self or match_in_children))
        return match_in_self or match_in_children

    def search_item_in_all_columns(self, item, filters):
        """任意关键字在任一列出现就算命中，如果 filters 为空总是返回 True
        如果匹配，增加高亮显示"""
        if not filters:
            # 清除所有高亮
            for col in range(item.columnCount()):
                item.setBackground(col, QColor('transparent'))
            return True

        match = False
        match_in_columns = set()

        for col in range(item.columnCount()):
            txt = item.text(col).lower()
            for kw in filters:
                if kw in txt:
                    match = True
                    match_in_columns.add(col)

        return match

    def expand_all_items(self, parent_item):
        """递归展开所有项"""
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)
            child_item.setExpanded(True)  # 展开当前项
            self.expand_all_items(child_item)  # 递归展开子项

    def open_setting_dialog(self):
        dialog = ConfigSettingDialog(self)
        dialog.exec_()

    def setup_log_viwer(self):
        if not hasattr(self, 'log_viewer'):
            self.log_viewer = QPlainTextEdit()
            self.log_viewer.setReadOnly(True)
            self.log_viewer.setFont(QFont("Consolas", 11))
            self.log_viewer.setStyleSheet(f"""
                QPlainTextEdit {{
                    background-color: #0e1117;
                    color: white;
                    border: 1px solid #2c2f36;
                    font-family: Consolas, monospace;
                    font-size: {2 * self.font_size}px;
                    padding: 10px;
                }}
                /* 纵向滚动条 */
                QTextEdit QScrollBar:vertical {{
                    background: transparent;
                    width: 8px;
                    margin: 0px;
                }}
                QTextEdit QScrollBar::handle:vertical {{
                    background: #555555;
                    border-radius: 4px;
                    min-height: 20px;
                }}
                QTextEdit QScrollBar::handle:vertical:hover {{
                    background: #888888;
                }}
                QTextEdit QScrollBar::add-line:vertical,
                QTextEdit QScrollBar::sub-line:vertical {{
                    height: 0px;
                    background: none;
                    border: none;
                }}
                QTextEdit QScrollBar::add-page:vertical, QTextEdit QScrollBar::sub-page:vertical {{
                    background: none;
                }}
    
                /* 横向滚动条 */
                QTextEdit QScrollBar:horizontal {{
                    background: transparent;
                    height: 8px;
                    margin: 0px;
                }}
                QTextEdit QScrollBar::handle:horizontal {{
                    background: #555555;
                    border-radius: 4px;
                    min-width: 20px;
                }}
                QTextEdit QScrollBar::handle:horizontal:hover {{
                    background: #888888;
                }}
                QTextEdit QScrollBar::add-line:horizontal,
                QTextEdit QScrollBar::sub-line:horizontal {{
                    width: 0px;
                    background: none;
                    border: none;
                }}
                QTextEdit QScrollBar::add-page:horizontal, QTextEdit QScrollBar::sub-page:horizontal {{
                    background: none;
                }}
            """)
            # 启用垂直滚动条自动到底部
            self.log_viewer.verticalScrollBar().rangeChanged.connect(
                lambda: self.log_viewer.verticalScrollBar().setValue(
                    self.log_viewer.verticalScrollBar().maximum()
                )
            )
            # 创建 sink
            self.text_logger = QTextEditLogger(self.log_viewer, max_lines=1000)
            logger.remove()
            logger.add(self.text_logger, format="{time:HH:mm:ss} | {level} | {message}", level="DEBUG")

    def toggle_log_viewer(self):
        self.log_anim.stop()

        if not self.log_expanded:
            self.right_log_panel.show()
            self.log_anim.setStartValue(0)
            self.log_anim.setEndValue(int(0.4 * self.window_height))  # 或你趋势面板目标高度
            self.log_anim.start()
            self.log_expanded = True
        else:
            self.log_anim.setStartValue(self.right_log_panel.height())
            self.log_anim.setEndValue(0)

            # 动画结束后再 hide
            def on_finished():
                self.right_log_panel.hide()
                self.log_anim.finished.disconnect(on_finished)
                self.log_expanded = False

            self.log_anim.finished.connect(on_finished)
            self.log_anim.start()

    def open_trend_analysis(self):
        # 假设你已有 point_fetchers 和 data_fetcher 两个属性
        dlg = TrendAnalysisDialog(
            point_fetchers=self.config.get_tools_by_type("point-search"),
            data_fetcher=self.config.get_tools_by_type("trenddb-fetcher")[0],
            parent=self
        )
        dlg.show()

    def show_app_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 6px;
                font-size: 11pt;
                padding: 4px 0px;
            }
            QMenu::item {
                padding: 0px;
                margin: 0px;
            }
            QMenu::item:selected {
                background-color: transparent;
            }
        """)

        self.add_menu_action(menu, "版本更新", "检查更新", self.updater.check_update)
        self.add_menu_action(menu, "关于", "关于", self.show_about_dialog)

        pos = self.menu_button.mapToGlobal(QPoint(0, 0))
        menu_width = menu.sizeHint().width()
        menu_height = menu.sizeHint().height()

        target_pos = QPoint(pos.x() - menu_width, pos.y() - menu_height)
        menu.exec_(target_pos)

    def show_about_dialog(self):
        QMessageBox.about(self, "关于",
                          f"配置编辑器 v{self.updater.current_version}\n"
                          "© 2025 Luculent\n"
                          "用于多配置文件编辑与管理")

    # 自定义方法添加图标+文本的菜单项
    def add_menu_action(self, menu, icon_name, text, callback):
        widget = QWidget(menu)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)  # 控制图标与文字间距

        icon_label = QLabel()
        icon = QIcon(get_icon(icon_name)).pixmap(20, 20)
        icon_label.setPixmap(icon)

        text_label = QLabel(text)
        text_label.setStyleSheet("font-size: 11pt;")

        layout.addWidget(icon_label)
        layout.addWidget(text_label)
        layout.addStretch()

        action = QWidgetAction(menu)
        action.setDefaultWidget(widget)
        menu.addAction(action)

        # 设置悬浮高亮
        widget.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
            QWidget:hover {
                background-color: #e6f7ff;
                border-radius: 4px;
            }
        """)

        def on_click(event):
            if event.button() == Qt.LeftButton:
                callback()
                menu.close()

        widget.mousePressEvent = on_click
