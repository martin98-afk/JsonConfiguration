import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette
from PyQt5.QtWidgets import QApplication, QStyleFactory
from PyQt5.QtGui import QColor

from application.utils.config_handler import load_config, save_history, save_config, HISTORY_PATH
from application.json_editor import JSONEditor


def rigister_parameter():
    # 装饰器，用于注册参数方法类
    def decorator(cls):
        return cls


def run_app():
    os.environ["OMP_NUM_THREADS"] = "3"
    app = QApplication(sys.argv)
    QApplication.setDoubleClickInterval(300)  # 全局设置为 300 毫秒
    # 设置应用程序级别样式
    QApplication.setStyle(QStyleFactory.create("Fusion"))
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    font = QFont("微软雅黑", 10)
    app.setFont(font)
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#f4f6f9"))
    app.setPalette(palette)
    editor = JSONEditor()
    editor.show()
    sys.exit(app.exec_())
