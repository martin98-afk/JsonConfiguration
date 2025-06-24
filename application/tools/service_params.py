import httpx
from loguru import logger

from application.base import BaseTool


class ServiceParamsFetcher(BaseTool):
    """
    支持单个或多个 point_path，并行 fetch 测点，增加设备名称获取的容错重试。
    """

    def __init__(
        self,
        prefix: str,
        api_key: str,
        service_params_path: str,
        max_workers: int = 10,
        **kwargs,
    ):
        super().__init__()
        self.base_url = prefix
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.service_params_path = service_params_path
        self.max_workers = max_workers

    def call(self, service_id: str) -> list[str]:
        """
        获取设备名称列表，带重试机制，避免超时导致失败。
        serviceVersionId=1915666374433177600
        """
        try:
            params = {"serviceVersionId": service_id}
            with httpx.Client(
                base_url=self.base_url, timeout=self.timeout
            ) as client:
                resp = client.get(
                    self.service_params_path, params=params, headers=self.headers
                )
            resp.raise_for_status()
            data = resp.json()
            logger.info(
                "服务参数请求成功: {} 个服务参数", len(data.get("data", []))
            )
            return [item["paramName"] for item in data["data"]]
        except Exception as e:
            logger.warning(f"获取服务参数失败，重试中: {e}")
            # 重试由 tenacity 处理，若超出重试将抛出
            raise
