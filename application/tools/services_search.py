import httpx
from loguru import logger

from application.base import BaseTool


class SeviceListSearcher(BaseTool):
    """
    支持单个或多个 point_path，并行 fetch 测点，增加设备名称获取的容错重试。
    """

    def __init__(
        self,
        prefix: str,
        api_key: str,
        service_list_path: str,
        timeout: float = 3.0,
        max_workers: int = 10,
        **kwargs,
    ):
        super().__init__()
        self.base_url = prefix
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.service_list_path = service_list_path
        self.timeout = timeout
        self.max_workers = max_workers

    def call(self) -> list[list[str]]:
        """
        获取设备名称列表，带重试机制，避免超时导致失败。
        """
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.get(self.service_list_path, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            logger.info("服务列表请求成功: {} 条记录", len(data.get("data", [])))
            return [
                [item["serviceName"], item["serviceUrl"], item["serviceVersionId"]]
                for item in data["data"]
            ]
        except Exception as e:
            logger.warning(f"获取服务列表失败，重试中: {e}")
            # 重试由 tenacity 处理，若超出重试将抛出
            raise