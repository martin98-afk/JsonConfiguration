import asyncio
import os
from collections import defaultdict

import aiohttp
import requests
from loguru import logger
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot, QThread


class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(object)  # 新增：用于发送每次获取到的部分结果


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            if isinstance(self.fn, list):
                result = defaultdict(list)
                for fetcher in self.fn:
                    if fetcher is None:
                        continue
                    r = fetcher.call(*self.args, **self.kwargs)
                    policy = self.kwargs.get("policy", "extend")
                    if r and policy == "extend":
                        for t, pts in r.items():
                            result[t].extend(pts)
                    elif r and policy == "update":
                        for t, pts in r.items():
                            result[t] = pts
                    self.signals.progress.emit(r)
            else:
                result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            import traceback
            logger.error(f"Worker error: {traceback.format_exc()}")
            self.signals.error.emit(traceback.format_exc())


class DownloadThread(QThread):
    progress_signal = pyqtSignal(int)  # 进度信号
    finished_signal = pyqtSignal(str)  # 完成信号（返回文件路径）
    error_signal = pyqtSignal(str)  # 错误信号
    canceled_signal = pyqtSignal()  # 取消信号（新增）

    def __init__(self, url, file_path, token):
        super().__init__()
        self.url = url
        self.file_path = file_path
        self.headers = {"Authorization": f"token {token}"} if token else {}
        self.is_canceled = False  # 取消标志位
        self.session = requests.Session()  # 使用 Session 以便关闭连接

    def run(self):
        try:
            response = self.session.get(self.url, headers=self.headers, stream=True, timeout=10)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(self.file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if self.is_canceled:  # 每次读取前检查取消标志
                        f.close()
                        os.remove(self.file_path)  # 删除不完整文件
                        self.canceled_signal.emit()
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress_signal.emit(progress)

            self.finished_signal.emit(self.file_path)
        except Exception as e:
            if not self.is_canceled:  # 非取消情况才触发错误信号
                self.error_signal.emit(str(e))
        finally:
            self.session.close()  # 确保释放网络资源


class AsyncUpdateChecker(QThread):
    finished = pyqtSignal(object)  # 返回 latest_release 或 None
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = parent.repo
        self.platform = parent.platform
        self.token = parent.token

    async def fetch_github(self):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        headers = headers | {"Authorization": f"token {self.token}"} if self.token else headers
        url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    self.error.emit(f"GitHub API 请求失败：{resp.status}")
                    return None

    async def fetch_gitee(self):
        headers = {"Authorization": f"token {self.token}"} if self.token else {}
        url = f"https://gitee.com/api/v5/repos/{self.repo}/releases/latest"
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    self.error.emit(f"Gitee API 请求失败：{resp.status}")
                    return None

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            if self.platform == "github":
                result = loop.run_until_complete(self.fetch_github())
            elif self.platform == "gitee":
                result = loop.run_until_complete(self.fetch_gitee())
            else:
                result = None
                self.error.emit("不支持的平台")
        except Exception as e:
            self.error.emit(str(e))
            result = None
        finally:
            self.finished.emit(result)
