"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: check_updates.py
@time: 2025/6/17 09:45
@desc: 
"""
import os
import sys
import requests
import hashlib
import subprocess


def check_update():
    # 检测服务器版本号
    server_version = requests.get("http://yourserver.com/version.json").json()
    current_version = "1.0.0"  # 从本地 versions.json 读取
    if server_version["version"] > current_version:
        # 下载更新包
        update_url = server_version["download_url"]
        update_path = "update_temp.exe"
        with open(update_path, "wb") as f:
            f.write(requests.get(update_url).content)

        # 创建更新脚本
        script = """@echo off
timeout /t 5 >nul
del /f /q "{main_exe}"
move /y "{update_path}" "{main_exe}"
start "" "{main_exe}"
""".format(main_exe=os.path.abspath(sys.argv[0]), update_path=update_path)
        with open("update.bat", "w") as f:
            f.write(script)

        # 启动更新并退出
        subprocess.Popen(["update.bat"], shell=True)
        sys.exit()


check_update()
