"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: utils.py
@time: 2025/4/27 10:03
@desc: 
"""
import os
import pickle
import re
import sys

from PyQt5 import sip
from PyQt5.QtGui import QFont, QIcon, QColor
from loguru import logger


def sanitize_path(path):
    # 定义需要替换的非法字符模式（包括常见操作系统不允许的字符）
    illegal_chars = r'[\\/:*?"<>|]'  # 可根据需求扩展字符集
    # 规范化路径并拆分处理每个层级
    normalized = os.path.normpath(path)
    parts = []
    while True:
        head, tail = os.path.split(normalized)
        if tail:
            parts.append(tail)
            normalized = head
        else:
            if head:
                parts.append(head)
            break
    # 反转并清理每个路径部分
    parts.reverse()
    cleaned = [re.sub(illegal_chars, '_', p) for p in parts]
    # 重新组合路径
    return os.path.join(*cleaned) if cleaned else ''


def save_point_cache(data, filename='point_cache.pkl'):
    with open(filename, 'wb') as f:
        pickle.dump(data, f)


def load_point_cache(filename='point_cache.pkl'):
    try:
        with open(filename, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return {}


def error_catcher_decorator(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            return None

    return wrapper


def get_file_name(path: str):
    return ".".join(os.path.basename(path).split(".")[:-1])


# 日期控件设置
def styled_dt(dt_edit):
    dt_edit.setCalendarPopup(True)
    dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
    dt_edit.setFont(QFont("Microsoft YaHei", 10))
    dt_edit.setStyleSheet("""
        QDateTimeEdit {
            padding: 4px;
            border: 1px solid #ccc;
            border-radius: 6px;
            background-color: #f9f9f9;
        }
        QToolButton {
            color: black;
            border-radius: 4px;
            padding: 2px 6px;
        }
    """)
    cal = dt_edit.calendarWidget()
    cal.setStyleSheet("""
        QWidget {
            color: black;
            background-color: white;
            font-family: "Microsoft YaHei";
            font-size: 10pt;
        }
        QToolButton {
            color: black;
            font-weight: bold;
            border-radius: 4px;
        }
        QToolButton:hover {
            background-color: #d0d0d0;
        }
        QCalendarWidget QTableView::item {
            padding: 4px;
            border-radius: 4px;
        }
        QCalendarWidget QTableView::item:hover {
            background-color: #e0e0e0;
            color: #000;
        }
        QCalendarWidget QTableView::item:selected {
            background-color: #c0c0c0;
        }
    """)
    return dt_edit


def resource_path(relative_path):
    """获取打包后资源文件的绝对路径"""
    if hasattr(sys, '_MEIPASS'):
        # 如果是打包后的环境
        base_path = sys._MEIPASS
    else:
        # 开发环境，直接使用当前路径
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_icon(icon_name):
    icons = {}
    relative_path = "icons"
    for name in os.listdir(resource_path(relative_path)):
        if name.endswith(".png"):
            icons[name[:-4]] = os.path.join(resource_path(relative_path), name)

    return QIcon(icons.get(icon_name, "icons/icon_unknown.png"))


def get_button_style_sheet(bg_color=None):
    bg_color = bg_color if bg_color else "#e9ecef"
    return f"""
            QPushButton {{
                background-color: {bg_color};
                border: none;
                border-radius: 6px;
                color: #495057;
                font-size: 15px;
                padding: 10px 10px;
                margin: 0px;
            }}
            QPushButton:hover {{
                background-color: #adb5bd;
                color: white;
            }}
            QPushButton:pressed {{
                background-color: #868e96;
            }}
            QPushButton:focus {{
                outline: none;
                border: none;
            }}
        """


def seed_everything(seed: int = 1):
    import random
    import os
    import numpy as np
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)