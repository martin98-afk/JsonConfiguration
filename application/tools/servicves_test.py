import httpx

from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtCore import QObject, pyqtSignal, QRunnable
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type,
    RetryError,
)


class ServiceTestFetchWorkerSignals(QObject):
    new_segment = pyqtSignal(int, dict)  # (segment_index, {point: value})
    finished = pyqtSignal()


class ServiceTestFetchWorker(QRunnable):
    def __init__(
        self, testor, service_url: str, points: list, values_list: list, ts_list: list
    ):
        super().__init__()
        self.testor = testor
        self.service_url = service_url
        self.points = points
        self.values_list = values_list
        self.ts_list = ts_list
        self.signals = ServiceTestFetchWorkerSignals()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        if hasattr(self.testor, "cancel"):
            self.testor.cancel()

    def run(self):
        data_list = [
            {
                "data": {
                    name: vals[i] for name, vals in zip(self.points, self.values_list)
                }
            }
            for i in range(len(self.ts_list))
        ]
        try:
            for idx, segment in self.testor.test(self.service_url, data_list):
                if self._cancelled:
                    break
                self.signals.new_segment.emit(idx, segment)
        except Exception as e:
            print(f"ServiceTestFetchWorker 异常: {e}")
        finally:
            self.signals.finished.emit()


class ServicesTest:
    def __init__(self, timeout=5.0, max_workers=5):
        self.timeout = timeout
        self.max_workers = max_workers
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _construct_response(self, result):
        data = result["data"]
        data_list = data["result"]
        names = [item["paramName"] for item in data["outputParams"]]
        return {name: val for name, val in zip(names, data_list)}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    )
    def _test_single(self, path, data) -> dict:
        if self._cancelled:
            raise Exception("Task cancelled")  # 主动抛异常，停止重试
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(path, json=data)
            resp.raise_for_status()
            if resp.json()["data"].get("flag", False):
                return self._construct_response(resp.json())
            else:
                return resp.json()

    def test(self, service: str, data_list: list[dict]):
        with ThreadPoolExecutor(max_workers=self.max_workers) as exe:
            future_map = {
                exe.submit(self._test_single, service, d): idx
                for idx, d in enumerate(data_list)
            }
            for fut in as_completed(future_map):
                if self._cancelled:
                    break
                idx = future_map[fut]
                try:
                    res = fut.result()
                    if res:
                        return res
                except RetryError as re:
                    print(f"段{idx}重试失败: {re}")
                except Exception as e:
                    print(f"段{idx}请求异常: {e}")


if __name__ == "__main__":
    testor = ServicesTest()
    service = (
        "http://172.16.134.122:8900/rest/di/service/modelPublish/1/1915666374399623168"
    )
    data_list = [{"data": {"point1": 1, "point2": 1, "point3": 1, "point4": 1}}]
    results = testor.test(service, data_list)
    test = ServiceTestFetchWorker(
        ServicesTest(),
        service,
        points=["point1", "point2", "point3", "point4"],
        sample=[
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1],
        ],
        ts_list=[1, 1, 1, 1, 1, 1, 1, 1],
    )
    result = test.run()
