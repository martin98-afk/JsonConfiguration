from collections import defaultdict
from loguru import logger
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot


class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)


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
                    r = fetcher.call()
                    if r:
                        for t, pts in r.items():
                            result[t].extend(pts)
            else:
                result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            import traceback
            logger.error(f"Worker error: {traceback.format_exc()}")
            self.signals.error.emit(traceback.format_exc())
