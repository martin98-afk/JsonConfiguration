"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: di_flow_params.py
@time: 2025/6/27 17:14
@desc: 
"""
import psycopg2

from loguru import logger
from psycopg2 import OperationalError

from application.base import BaseTool


class DiFlow(BaseTool):

    def __init__(self,
                 host: str="172.16.134.122",
                 port: str="5030",
                 user: str="postgres",
                 password: str="Sushine@2024Nov!",
                 database: str="sushine_business",
                 parent=None):
        super().__init__(parent)
        self.conn_params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database
        }

    # 查询数据
    def get_flows(self):
        with psycopg2.connect(**self.conn_params) as conn:
            try:
                cur = conn.cursor()
                cur.execute(f"SELECT DISTINCT flow_nam FROM di_flow")  # 替换为你的查询语句
                rows = cur.fetchall()
                return [row[0] for row in rows]
            except OperationalError as e:
                logger.error(f"模型画布查询失败: {e}")

    def call(self):

        return self.get_flows()


if __name__ == "__main__":
    flows = DiFlow()
    result = flows.call()
