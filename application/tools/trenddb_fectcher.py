import httpx
import numpy as np

from datetime import datetime
from typing import Dict, Tuple, List
from loguru import logger
from application.base import BaseTool


class TrenddbFetcher(BaseTool):

    def __init__(
            self, base_url: str, api_key: str, path: str, max_workers=10, **kwargs
    ):
        super().__init__()
        self.base_url = base_url
        self.path = path
        self.api_key = api_key
        self.max_workers = max_workers

    def call(
            self,
            tag_name: str,
            start_time: datetime,
            end_time: datetime,
            data_num: int = 2000,
            **kwargs
    ) -> dict[str, Tuple[np.ndarray, np.ndarray]]:
        """从API获取数据"""
        params = {
            "startTime": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "tagNames[]": tag_name,
            "dataNum": data_num,
        }

        try:
            with httpx.Client(base_url=self.base_url) as client:
                response = client.get(url=self.path, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data["success"]:
                    items = data["result"]["items"]
                    if items:
                        points = items[0]["value"]
                        times = [
                            datetime.strptime(
                                p["timeStamp"], "%Y-%m-%d %H:%M:%S"
                            ).timestamp()
                            for p in points
                        ]
                        values = [p["value"] for p in points]
                        return {tag_name: (np.array(times), np.array(values))}
            return {}
        except Exception as e:
            import traceback

            logger.error(f"数据获取失败: {traceback.format_exc()}")
            return {}

    def call_batch(
            self,
            tag_names: List[str],
            start_time: datetime,
            end_time: datetime,
            data_num: int = 2000,
            **kwargs
    ) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        """
        单次请求批量获取多个测点的时序数据

        返回:
            dict[tag_name] = (times: np.ndarray, values: np.ndarray)
        """
        params = [
            ("startTime", start_time.strftime("%Y-%m-%d %H:%M:%S")),
            ("endTime", end_time.strftime("%Y-%m-%d %H:%M:%S")),
            ("dataNum", str(data_num)),
        ]
        # 添加多个 tagNames[] 参数
        for name in tag_names:
            params.append(("tagNames[]", name))

        results: Dict[str, Tuple[np.ndarray, np.ndarray]] = {
            name: (None, None) for name in tag_names
        }
        try:
            with httpx.Client(base_url=self.base_url) as client:
                response = client.get(
                    url=self.path,
                    params=params,
                    timeout=10,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            response.raise_for_status()
            payload = response.json()

            if payload.get("success") and payload.get("result"):
                items = payload["result"].get("items", [])
                for item in items:
                    name = (
                        item.get("name").split(".")[1]
                        if "." in item.get("name")
                        else item.get("name")
                    )
                    points = item.get("value", [])
                    # 解析时间戳列表和值列表
                    times = [
                        datetime.strptime(
                            p["timeStamp"], "%Y-%m-%d %H:%M:%S"
                        ).timestamp()
                        for p in points
                    ]
                    values = [p["value"] for p in points]
                    results[name] = (np.array(times), np.array(values))
            logger.info(
                f"成功获取时序数据, 测点数: {len(results)} 数据长度: {[len(value[0]) if value else 0 for value in results.values()]}"
            )
        except Exception as e:
            import traceback
            logger.error(f"数据获取失败: {traceback.format_exc()}")
            raise

        return results
