"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: conn_postgres.py
@time: 2025/6/27 11:57
@desc: 
"""
import json
import sys

import psycopg2
from PyQt5.QtCore import Qt
from psycopg2 import OperationalError
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QFormLayout,
    QScrollArea, QMessageBox, QStatusBar, QTreeWidget, QTreeWidgetItem
)


# 连接数据库
def create_connection():
    try:
        conn = psycopg2.connect(
            host="172.16.134.122",  # 数据库主机地址
            database="sushine_business",  # 数据库名称
            user="postgres",  # 用户名
            password="Sushine@2024Nov!",  # 密码
            port="5030"  # 端口号（默认5432）
        )
        print("成功连接数据库")
        return conn
    except OperationalError as e:
        print(f"连接失败: {e}")
        return None


# 查询数据
def get_flow_nodes(conn, flow_nam='能耗优化模型(v6)'):
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT flow_json FROM di_flow where flow_nam='{flow_nam}'")  # 替换为你的查询语句
        rows = cur.fetchall()
        return {
            dict["name"].split("-")[1]: (dict["text"], dict["id"])
            for dict in json.loads(rows[0][0])["pens"] if "unit" in dict["name"]
        }
    except OperationalError as e:
        print(f"查询失败: {e}")


# 查询组件参数
def get_unit_params(conn, unit_no):
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT param_no, field_type, param_name, default_val FROM di_unit_param where unit_no='{unit_no}'")  # 替换为你的查询语句
        rows = cur.fetchall()
        return {row[0]: (row[1], row[2], row[3]) for row in rows}
    except OperationalError as e:
        print(f"查询失败: {e}")


# 查询组件参数
def get_node_params_value(conn, node_no):
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT param_no, unit_param_no, param_val FROM di_flow_node_param where node_no='{node_no}'")  # 替换为你的查询语句
        rows = cur.fetchall()
        return {row[0]: (row[1], row[2]) for row in rows}
    except OperationalError as e:
        print(f"查询失败: {e}")


# 修改数据（插入/更新/删除）
def modify_data(conn, param_no, param_val):
    try:
        cur = conn.cursor()
        # 示例：更新数据
        cur.execute("UPDATE di_flow_node_param SET param_val = %s WHERE param_no = %s;", (param_val, param_no))
        conn.commit()  # 提交事务
        print("数据修改成功")
    except OperationalError as e:
        print(f"修改失败: {e}")
        conn.rollback()  # 回滚事务


class ParamEditor(QWidget):
    def __init__(self, node_id, params, parent=None):
        super().__init__(parent)
        self.node_id = node_id
        self.params = params
        self.controls = {}

        layout = QFormLayout()
        for param_key, (field_type, param_name, default_val, unit_type) in params.items():
            label = QLabel(param_name)
            if field_type == "text":
                edit = QLineEdit(default_val or "")
            elif field_type == "int":
                edit = QLineEdit(default_val or "0")
            else:
                edit = QLineEdit(default_val or "")

            edit.setObjectName(param_key)
            edit.textChanged.connect(self.on_edit_changed)
            self.controls[param_key] = edit
            layout.addRow(label, edit)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setLayout(layout)
        scroll.setWidget(scroll_content)

        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    def on_edit_changed(self):
        sender = self.sender()
        param_key = sender.objectName()
        value = sender.text()

        try:
            modify_data(connection, param_key, value)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"更新参数失败: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("参数配置工具")
        self.setGeometry(100, 100, 800, 600)

        self.init_ui()
        self.load_data()

    def init_ui(self):
        # 主布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout()

        # 左侧：节点列表
        self.node_tree = QTreeWidget()
        self.node_tree.setHeaderLabels(["组件名称", "参数名", "值", "类型"])
        self.node_tree.itemSelectionChanged.connect(self.on_node_selected)

        # 右侧：参数编辑区域
        self.param_editor = QWidget()
        self.param_layout = QVBoxLayout()
        self.param_editor.setLayout(self.param_layout)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.param_editor)

        layout.addWidget(self.node_tree, 1)
        layout.addWidget(scroll, 3)

        main_widget.setLayout(layout)

        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")

    def load_data(self):
        global connection
        connection = create_connection()
        if not connection:
            QMessageBox.critical(self, "错误", "无法连接数据库")
            return

        self.flow_nodes = get_flow_nodes(connection)
        if not self.flow_nodes:
            QMessageBox.critical(self, "错误", "未找到流程节点")
            return

        self.flow_params = {
            id: get_unit_params(connection, id)
            for id in self.flow_nodes
            if len(get_unit_params(connection, id)) > 0
        }

        self.flow_params_value = {}
        for key, value in self.flow_nodes.items():
            node_no = value[1]
            results = get_node_params_value(connection, node_no)
            if len(results) > 0:
                self.flow_params_value[node_no] = {
                    k: (v[0], v[1], self.flow_params.get(key, {}).get(v[0], ("", ""))[1],
                        self.flow_params.get(key, {}).get(v[0], ("", ""))[0])
                    for k, v in results.items()
                }
                # self.flow_params_value[node_no]["name"] = value[0]

                # 创建树节点
                parent_item = QTreeWidgetItem([value[0], "", "", ""])
                parent_item.setData(0, Qt.UserRole, node_no)  # 存储 node_no

                for param_key, (unit_param_no, param_name, param_val, field_type) in self.flow_params_value[
                    node_no].items():
                    child_item = QTreeWidgetItem([
                        "",
                        param_name,
                        str(param_val),
                        field_type
                    ])
                    child_item.setData(0, Qt.UserRole, param_key)
                    parent_item.addChild(child_item)

                self.node_tree.addTopLevelItem(parent_item)

        self.statusBar.showMessage("数据加载完成")

    def on_node_selected(self):
        selected_item = self.node_tree.currentItem()
        if not selected_item:
            return

        node_no = selected_item.data(0, Qt.UserRole)
        if not node_no:
            node_no = selected_item.parent().data(0, Qt.UserRole)

        if not node_no:
            return

        # 清除旧控件
        for i in reversed(range(self.param_layout.count())):
            self.param_layout.itemAt(i).widget().setParent(None)

        params = self.flow_params_value.get(node_no, {})
        if not params:
            label = QLabel("无可用参数")
            self.param_layout.addWidget(label)
            return

        editor = ParamEditor(node_no, params)
        self.param_layout.addWidget(editor)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
