import httpx

from loguru import logger
from typing import List, Dict
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from application.base import BaseTool


class RTSPSearcher(BaseTool):
    """
    支持单个或多个 point_path，并行 fetch 测点，增加设备名称获取的容错重试。
    """

    def __init__(self, prefix: str, api_key: str, dev_name_path: str, point_path: Dict[str, str], max_workers: int = 10,
                 **kwargs):
        super().__init__()
        self.base_url = prefix
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.dev_name_path = dev_name_path
        # 支持传入字符串或列表
        self.point_paths = point_path
        self.max_workers = max_workers
        # 获取设备映射，自动重试
        try:
            self._dev_name_dict = self._get_dev_name()
        except:
            import traceback
            logger.error(f"设备名获取失败！")
            self._dev_name_dict = {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
    )
    def _get_dev_name(self) -> Dict[str, str]:
        """
        获取设备名称列表，带重试机制，避免超时导致失败。
        """
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.get(self.dev_name_path, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            logger.info("设备名称请求成功: {} 条记录", len(data.get('data', [])))
            return self._create_pid_name_map_with_check(data)
        except Exception as e:
            logger.warning(f"获取设备名称失败，重试中: {e}")
            # 重试由 tenacity 处理，若超出重试将抛出
            raise

    def _create_pid_name_map_with_check(self, data) -> Dict[str, str]:
        result = {}
        duplicates = set()

        def process_node(node):
            if 'pId' in node and 'name' in node:
                if node['pId'] in result:
                    duplicates.add(node['pId'])
                result[node['pId']] = node['name']
            for child in node.get('children', []):
                process_node(child)

        for item in data.get('data', []):
            process_node(item)

        if duplicates:
            logger.warning(f"发现重复ID: {', '.join(duplicates)}")
        return result

    def _fetch_single_dev_points(
            self,
            dev_name: str,
            param_type: str,
            point_path: str
    ) -> List[Dict[str, str]]:
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.get(point_path, headers=self.headers)
                resp.raise_for_status()
                data = resp.json()
                return self._parse_param(data, dev_name, param_type)
        except Exception as e:
            logger.warning(f"[{param_type}|{dev_name}|{point_path}] 请求失败：{e}")
            return []

    def _parse_param(
            self,
            resp,
            dev_name: str,
            param_type: str
    ) -> List[Dict[str, str]]:
        point_list = []
        for item in resp.get("data", []):
            cameraName = item["cameraName"].split(";")
            previewUrl = item.get("previewUrl", "").split(";")
            for pt, nm in zip(previewUrl, cameraName):
                point_dict = {
                    "设备名": dev_name,
                    "监控点名称": nm,
                    "测点名": pt
                }
            point_list.append(point_dict)

        return point_list

    def call(self) -> Dict[str, Dict[str, str]]:
        """
        并发搜索所有 dev_id 与所有 point_paths 组合的测点。
        若设备名称加载失败，会抛出异常。
        """
        logger.info("开始并发搜索测点信息...")
        results = defaultdict(list)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures_dict = defaultdict(list)
            for ptype, path in self.point_paths.items():
                if "&eqlevelNo=" in path:
                    for dev_id, dev_name in self._dev_name_dict.items():
                        future = executor.submit(
                            self._fetch_single_dev_points,
                            dev_name, ptype, path.replace("&eqlevelNo=", f"&eqlevelNo={dev_id}")
                        )
                        futures_dict[ptype].append(future)

            for ptype in futures_dict:
                for fut in as_completed(futures_dict[ptype]):
                    try:
                        data = fut.result()
                        if len(data) == 0: continue
                        results[ptype].extend(data)
                    except Exception as e:
                        logger.error(f"搜索任务异常：{e}")
        logger.info(f"搜索完成，总共 {sum([len(item) for _, item in results.items()])} 条测点")

        return results
