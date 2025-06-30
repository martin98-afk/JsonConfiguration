"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: di_flow_params.py
@time: 2025/6/27 17:14
@desc: 
"""
import copy
import json
import psycopg2

from collections import defaultdict
from loguru import logger
from psycopg2 import OperationalError

from application.base import BaseTool


class DiFlowParams(BaseTool):

    def __init__(self,
                 host: str = "172.16.134.122",
                 port: str = "5030",
                 user: str = "postgres",
                 password: str = "Sushine@2024Nov!",
                 database: str = "sushine_business",
                 parent=None):
        super().__init__(parent)
        self.type_dict = {
            "1": "dropdown",
            "2": "dropdown",
            "10": "upload"
        }
        self.conn_params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database
        }

    # 查询数据
    def get_flow_nodes(self, conn, flow_nam='能耗优化模型(v6)'):
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT flow_json FROM di_flow where flow_nam='{flow_nam}'")  # 替换为你的查询语句
            rows = cur.fetchall()
            return {
                dict["id"]: (dict["text"], dict["name"].split("-")[1])
                for dict in json.loads(rows[0][0])["pens"] if "unit" in dict["name"]
            }
        except OperationalError as e:
            logger.error(f"画布流程查询失败: {e}")

    # 查询组件参数
    def get_unit_params(self, conn, unit_no):
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT param_no, field_type, param_name, default_val FROM di_unit_param where unit_no='{unit_no}'")  # 替换为你的查询语句
            rows = cur.fetchall()
            return {row[0]: (row[1], row[2], row[3]) for row in rows}
        except OperationalError as e:
            logger.error(f"组件参数查询失败: {e}")

    # 查询组件参数
    def get_node_params_value(self, conn, node_no):
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT param_no, unit_param_no, param_val FROM di_flow_node_param where node_no='{node_no}'")  # 替换为你的查询语句
            rows = cur.fetchall()
            return {row[0]: (row[1], row[2]) for row in rows}
        except OperationalError as e:
            logger.error(f"参数数值查询失败: {e}")

    def get_node_params_options(self, conn, param_no):
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT option_val, option_nam FROM di_unit_param_option where param_no='{param_no}'")  # 替换为你的查询语句
            rows = cur.fetchall()
            return {row[0]: row[1] for row in rows}
        except OperationalError as e:
            logger.error(f"下拉参数候选值查询失败: {e}")

    def call(self, prefix: str, service_name: str):
        with psycopg2.connect(**self.conn_params) as conn:
            flow_nodes = self.get_flow_nodes(conn, service_name)
            if not flow_nodes:
                logger.error(f"未找到 {service_name} 的流程内容！")
                return

            flow_params = {
                value[1]: self.get_unit_params(conn, value[1])
                for value in set(flow_nodes.values())
            }
            option2val = {}
            flow_params_value = defaultdict(dict)
            for key, value in flow_nodes.items():
                results = self.get_node_params_value(conn, key)
                if len(results) > 0:
                    for k, v in results.items():
                        name = flow_params.get(value[1], {}).get(v[0], ("", ""))[1]
                        type = flow_params.get(value[1], {}).get(v[0], ("", ""))[0]
                        if type not in ["3", "7", "8"]:  # 去除特征、标签、预测字段选择
                            if type == "1":
                                select_options = ["否", "是"]
                                option2val[k] = {v: k for k, v in enumerate(select_options)}
                                flow_params_value[key] = flow_params_value[key] | {
                                    k: {
                                        "param_name": name,
                                        "default": select_options[int(v[1])] if v[1] else "",
                                        "type": self.type_dict.get(type, "text"),
                                        "options": select_options
                                    }
                                }
                            elif type == "2":
                                options = self.get_node_params_options(conn, v[0])
                                option2val[k] = {v: k for k, v in options.items()}
                                flow_params_value[key] = flow_params_value[key] | {
                                    k: {
                                        "param_name": name,
                                        "default": options[v[1]],
                                        "type": self.type_dict.get(type, "text"),
                                        "options": list(options.values())
                                    }
                                }
                            else:
                                flow_params_value[key] = flow_params_value[key] | {
                                    k: {
                                        "param_name": name,
                                        "default": v[1],
                                        "type": self.type_dict.get(type, "text"),
                                    }
                                }

                    if not flow_params_value[key]:
                        flow_params_value.pop(key)
                        continue
                    flow_params_value[key]["name"] = value[0]

        # 构建参数读取结构
        structure_params = copy.deepcopy(flow_params_value)
        children = {}
        for key, param in structure_params.items():
            children = children | {
                param.pop("name"): {
                    "type": "group",
                    "children": {
                        value.pop("param_name"): value | {"id": key}
                        for key, value in param.items()
                    }
                }
            }
        param_structure = {
            f"{prefix}{service_name}": {
                "type": "group",
                "children": children
            }
        }

        return flow_params_value, param_structure, option2val


if __name__ == "__main__":
    flow_params = DiFlowParams()
    result = flow_params.call("能耗优化模型(v6)")
