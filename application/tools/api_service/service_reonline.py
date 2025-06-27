"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: service_reonline.py
@time: 2025/6/16 09:52
@desc: 
"""
import httpx
from loguru import logger

from application.base import BaseTool


class ServiceReonline(BaseTool):
    """
    用于将异常下线、服务日志卡死服务重新下线再上线
    """

    def __init__(self, base_url: str, api_key: dict, service_online_path: str, service_outline_path: str, **kwargs):
        """
        初始化日志查询器。

        :param base_url: API 基础 URL
        :param headers: HTTP 请求头（如认证信息）
        :param timeout: HTTP 请求超时时间
        """
        super().__init__()
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.service_online_path = service_online_path
        self.service_outline_path = service_outline_path

    def call(self, service_version_id: str) -> str:
        """
        获取指定服务版本的日志。

        :param service_id: 服务 ID
        :return: 日志内容字符串
        :raises: 若日志获取失败时抛出异常
        """
        params = {"serviceVersionId": service_version_id}
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            resp = client.post(self.service_outline_path, data=params, headers=self.headers)
        resp.raise_for_status()

        data = resp.json()
        if data.get("state") != "success" or data.get("code") != 0:
            raise Exception(f"接口异常: {data.get('message')}")

        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            resp = client.post(self.service_online_path, data=params, headers=self.headers)
        resp.raise_for_status()

        data = resp.json()
        if data.get("state") != "success" or data.get("code") != 0:
            raise Exception(f"接口异常: {data.get('message')}")

        logger.info(f"服务 {service_version_id} 已重新上线")


if __name__ == "__main__":
    pass
