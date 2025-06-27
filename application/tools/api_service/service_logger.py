"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: service_logger.py
@time: 2025/5/14 11:02
@desc: 
"""

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from application.base import BaseTool


class ServiceLogger(BaseTool):
    """
    用于查询服务日志的类，依赖服务搜索器的配置。
    """

    def __init__(self, base_url: str, api_key: dict, service_state_path: str, service_log_path: str, **kwargs):
        """
        初始化日志查询器。

        :param base_url: API 基础 URL
        :param headers: HTTP 请求头（如认证信息）
        :param timeout: HTTP 请求超时时间
        """
        super().__init__()
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.service_state_path = service_state_path
        self.service_log_path = service_log_path

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
    )
    def get_online_service_version(self, service_id: str) -> str:
        """
        获取指定服务的在线版本 ID。

        :param service_id: 服务 ID
        :return: 在线服务版本 ID
        :raises: 若未找到在线版本或请求失败时抛出异常
        """
        try:
            params = {"page": 1, "serviceId": service_id}
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.get(self.service_state_path, params=params, headers=self.headers)
            resp.raise_for_status()

            data = resp.json()
            if data.get("state") != "success" or data.get("code") != 0:
                raise Exception(f"接口异常: {data.get('message')}")

            online_versions = [
                item for item in data.get("data", [])
                if item.get("onlineStt") == "0"  # 在线状态标识
            ]

            if not online_versions:
                raise Exception("未找到在线服务版本")

            service_version_id = online_versions[0]["serviceVersionId"]
            logger.info(f"服务 {service_id} 的在线版本 ID: {service_version_id}")
            return service_version_id

        except Exception as e:
            logger.warning(f"获取在线服务版本失败: {e}")
            raise

    def call(self, service_version_id: str) -> str:
        """
        获取指定服务版本的日志。

        :param service_id: 服务 ID
        :return: 日志内容字符串
        :raises: 若日志获取失败时抛出异常
        """
        params = {"serviceVersionId": service_version_id}
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            resp = client.get(self.service_log_path, params=params, headers=self.headers)
        resp.raise_for_status()

        data = resp.json()
        if data.get("state") != "success" or data.get("code") != 0:
            raise Exception(f"接口异常: {data.get('message')}")

        log_content = data.get("data", "")
        logger.info(f"获取日志成功，内容长度: {len(log_content)} 字符")
        return log_content



if __name__ == "__main__":
    log = ServiceLogger(base_url="http://168.168.10.110:83",
                        api_key="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiIsImtpZCI6IjAwMiJ9.eyJ0ZW5hbnROYW0iOiLnp5_miLfnrqHnkIblhazlj7giLCJvcmdOYW1lIjoi54Wk55-_5oC76KeIIiwiaXNzIjoiU1lTIiwidXNyUm9sZSI6IlNZUyxHRFRITjAwMSxZWFpHMDAwMyxHRFRITjAwMixZV1JZMDA0IiwiYWRtaW5GbGciOiIxIiwib3JnSWQiOiIxNDYxNTk0NTQ1MDgxODEwOTQ0IiwidXNyTmFtIjoi57O757uf566h55CG5ZGYIiwidGVuYW50Tm8iOiIxIiwid2ViU29ja2V0SXAiOiJkZWZhdWx0IiwiaWF0IjoxNzQ3MTkyMjUxLCJrYXQiOjE3NDcxODI1MjcxNjJ9.xxnAp_CxsdL42o_bHiYcZ9_T6uUGIj62xI5yzEJ_trg")
    service_version_id = log.get_online_service_version("1917135632749035520")
    print(log.get_service_log(service_version_id))
