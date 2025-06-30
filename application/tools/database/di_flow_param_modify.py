"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: di_flow_param_modify.py
@time: 2025/6/30 10:54
@desc: 
"""
import psycopg2
from loguru import logger
from psycopg2 import OperationalError

from application.base import BaseTool


class DiFlowParamsModify(BaseTool):

    def __init__(self,
                 host: str = "172.16.134.122",
                 port: str = "5030",
                 user: str = "postgres",
                 password: str = "Sushine@2024Nov!",
                 database: str = "sushine_business",
                 parent=None):
        super().__init__(parent)
        self.conn_params = {
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "database": database
            }

    # 修改数据（插入/更新/删除）
    def modify_data(self, param_no, param_val):
        with psycopg2.connect(**self.conn_params) as conn:
            try:
                cur = conn.cursor()
                # 示例：更新数据
                cur.execute("UPDATE di_flow_node_param SET param_val = %s WHERE param_no = %s;", (param_val, param_no))
                conn.commit()  # 提交事务
                logger.info(f"参数节点 {param_no} 修改成功，修改后值为 {param_val}")
            except OperationalError as e:
                logger.error(f"参数节点修改失败: {e}")
                conn.rollback()  # 回滚事务

    def call(self, param_no: str, param_val: str):
        self.modify_data(param_no, param_val)