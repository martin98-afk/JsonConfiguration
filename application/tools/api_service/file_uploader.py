"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: file_uploader.py
@time: 2025/4/21 14:21
@desc: 
"""
import os
import tempfile
import zipfile
from typing import Optional, Dict
import httpx
from loguru import logger

from application.base import BaseTool


class DatasetUploader(BaseTool):
    """
    DatasetUploader 用于：
      1. 上传本地文件或文件夹到 dataset/upload 接口（自动压缩为 ZIP），获取返回的 data.filePath 和 data.fileName。
      2. 调用 dataset/add 接口，保存一条记录（表单 form-data 方式）。
    """

    def __init__(self, base_url: str, api_key: str = "", upload_path: str = "/rest/di/dataset/upload",
                 add_path: str = "/rest/di/dataset/add", **kwargs):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.upload_path = upload_path
        self.add_path = add_path
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def _ensure_zip(self, input_path: str) -> (str, bool):
        """
        如果输入不是 ZIP 文件，则自动压缩（文件或目录）为临时 ZIP。
        返回 (zip_path, is_temp)，is_temp 表示是否为临时文件，需要上传后删除。
        """
        if os.path.isfile(input_path) and input_path.lower().endswith(".zip"):
            return input_path, False

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        tmp_zip_path = tmp.name
        tmp.close()

        with zipfile.ZipFile(tmp_zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
            if os.path.isfile(input_path):
                zipf.write(input_path, arcname=os.path.basename(input_path))
            else:
                for root, dirs, files in os.walk(input_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start=input_path)
                        zipf.write(file_path, arcname=arcname)

        logger.info(f"已自动压缩为 ZIP: {tmp_zip_path}")
        return tmp_zip_path, True

    def upload_file(self, file_path: str) -> Optional[Dict[str, str]]:
        """
        上传文件/文件夹，自动压缩ZIP后上传，返回 {'filePath': ..., 'fileName': ...} 或 None
        """
        if not os.path.exists(file_path):
            logger.error(f"路径不存在：{file_path}")
            return None

        zip_path, is_temp = self._ensure_zip(file_path)
        url = f"{self.base_url}{self.upload_path}"
        try:
            with open(zip_path, "rb") as f:
                files = {"file": (os.path.basename(zip_path), f)}
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=self.headers, files=files)
                resp.raise_for_status()
                result = resp.json()

            if result.get("state") == "success" and isinstance(result.get("data"), dict):
                data = result["data"]
                fp = data.get("filePath")
                fn = data.get("fileName")
                if fp and fn:
                    logger.info(f"文件上传成功: {fn} -> {fp}")
                    return {"filePath": fp, "fileName": fn}
                logger.error(f"上传返回缺少 filePath/fileName: {result}")
            else:
                logger.error(f"上传失败，返回信息: {result}")
        except httpx.RequestError as exc:
            logger.error(f"上传请求错误：{exc}")
        except httpx.HTTPStatusError as exc:
            logger.error(f"上传 HTTP 错误：{exc}")
        except Exception as exc:
            logger.error(f"上传时其他错误：{exc}")
        finally:
            if is_temp:
                try:
                    os.remove(zip_path)
                    logger.debug(f"已删除临时ZIP: {zip_path}")
                except Exception:
                    pass
        return None

    def save_record(
            self,
            dataset_name: str,
            dataset_desc: str,
            tree_name: str,
            tree_no: str,
            file_path: str,
            file_name: str,
    ) -> dict:
        """
        保存记录（表单请求），返回 True/False
        """
        url = f"{self.base_url}{self.add_path}"
        data = {
            "datasetName": dataset_name,
            "datasetDesc": dataset_desc,
            "treeName": tree_name,
            "treeNo": tree_no,
            "filePath": file_path,
            "fileName": file_name,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=self.headers, data=data)
            resp.raise_for_status()
            result = resp.json()
            # 假设返回字段 code == 0 表示成功
            if result.get("code") == 0:
                logger.info(f"保存记录成功: {data}")
                return data
            else:
                logger.error(f"保存记录失败, 返回信息: {result}")
        except httpx.RequestError as exc:
            logger.error(f"保存记录请求错误：{exc}")
        except httpx.HTTPStatusError as exc:
            logger.error(f"保存记录 HTTP 错误：{exc}")
        except Exception as exc:
            logger.error(f"保存记录时其他错误：{exc}")
        return {}

    def call(
            self,
            file_path: str,
            dataset_name: str,
            dataset_desc: str,
            tree_name: str,
            tree_no: str,
    ) -> dict:
        """
        一体化：先上传文件，再保存记录
        """
        info = self.upload_file(file_path)
        if not info:
            logger.error("上传文件失败，无法保存记录")
            return {}
        return self.save_record(
            dataset_name=dataset_name,
            dataset_desc=dataset_desc,
            tree_name=tree_name,
            tree_no=tree_no,
            file_path=info["filePath"],
            file_name=info["fileName"],
        )
