import os.path
import shutil
import yaml

from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtCore import QObject, pyqtSignal, QThreadPool

from application.tools.api_service.file_uploader import DatasetUploader
from application.tools.api_service.point_search import PointSearcher
from application.tools.api_service.rtsp_search import RTSPSearcher
from application.tools.api_service.service_logger import ServiceLogger
from application.tools.api_service.service_params import ServiceParamsFetcher
from application.tools.api_service.service_reonline import ServiceReonline
from application.tools.api_service.services_search import SeviceListSearcher
from application.tools.api_service.trenddb_fectcher import TrenddbFetcher
from application.tools.database.di_flow import DiFlow
from application.tools.database.di_flow_param_modify import DiFlowParamsModify
from application.tools.database.di_flow_params import DiFlowParams
from application.utils.threading_utils import Worker
from application.utils.utils import resource_path


class ParamConfigLoader(QObject):
    params_loaded = pyqtSignal()

    def __init__(self, param_definitions_path="default.yaml"):
        super().__init__()
        self.param_definitions_path = param_definitions_path
        # 如果默认配置不存在，则复制一份备用配置
        if not os.path.exists(param_definitions_path):
            self.restore_default_params()
        self.title = "Json配置工具"
        self.threadpool = QThreadPool.globalInstance()

    def _reset_config(self):
        # 还原所有配置
        self.patch_info = {}
        self.param_structure = {}
        self.init_params = {}
        self.params_type = {}
        self.params_default = {}
        self.params_options = {}
        self.subchildren_default = {}
        self.model_binding_structure = {}
        self.api_tools = {}
        self.tab_names = {}
        self.tool_type_dict = {}
        self.param_templates = {}

    def restore_default_params(self):
        # 读取默认的yaml配置，并保存到本地
        try:
            shutil.copy(resource_path("default.yaml"), "default.yaml")
        except:
            logger.error("Failed to copy default.yaml")
        self.param_definitions_path = "default.yaml"

    def _read_config(self):
        with open(self.param_definitions_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        return cfg

    # ==============================
    # ✅ 公共接口
    # ==============================
    def load_async(self):
        self._reset_config()
        self.load_params_async()
        self.load_tools_async()

    def load_tools_async(self):
        """异步加载全部配置"""
        cfg = self._read_config()
        cfg = cfg.get("api-tools", cfg.get("api-search", {}))
        postgres_cfg = {"postgres": cfg.pop("postgres", {})}
        logger.info("Launching asynchronous tools load!")
        worker1 = Worker(self._load_tools_parallel, cfg)
        worker1.signals.finished.connect(
            lambda _: (logger.info("API Tools async load finished"))
        )
        worker1.signals.error.connect(
            lambda err: logger.error("Async full load api tools error: {}", err)
        )
        self.threadpool.start(worker1)

        worker2 = Worker(self._load_tools_parallel, postgres_cfg)
        worker2.signals.finished.connect(
            lambda _: (logger.info("Database Tools async load finished"))
        )
        worker2.signals.error.connect(
            lambda err: logger.error("Async full load database tools error: {}", err)
        )
        self.threadpool.start(worker2)

    def load_params_async(self):
        """异步加载全部配置"""
        logger.info("Launching asynchronous params load")
        worker = Worker(self.load_params)
        worker.signals.finished.connect(
            lambda _: (
                logger.info("Params async load finished"),
                self.params_loaded.emit(),
            )
        )
        worker.signals.error.connect(
            lambda err: logger.error("Async params load error: {}", err)
        )
        self.threadpool.start(worker)

    # ==============================
    # 🔧 工具加载函数
    # ==============================
    def _load_tools_parallel(self, cfg: dict) -> dict:
        """并行加载工具实例"""
        # 优先加载postgres工具
        logger.debug("Parallel tool load started for tools: {}", list(cfg.keys()))
        tool_list = {}
        # 增加连接postgres数据库的工具
        if "postgres" in cfg:
            postgres_cfg = cfg.pop("postgres", {})
            tool_list["di_flow"] = DiFlow(**postgres_cfg)
            tool_list["di_flow_params"] = DiFlowParams(**postgres_cfg)
            tool_list["di_flow_params_modify"] = DiFlowParamsModify(**postgres_cfg)
            self.api_tools.update(tool_list)
            return

        global_prefix = cfg.pop("prefix", "")
        global_api_key = cfg.pop("api-key", "")

        def create_searcher(tool_name, cfg_tool):
            prefix = cfg_tool.pop("prefix", global_prefix)
            api_key = cfg_tool.pop("api-key", global_api_key)
            tool_type = cfg_tool.get("type")
            if tool_type == "point-search":
                return tool_name, tool_type, PointSearcher(prefix, api_key, **cfg_tool)
            elif tool_type == "rtsp-search":
                return tool_name, tool_type, RTSPSearcher(prefix, api_key, **cfg_tool)
            elif tool_type == "file-upload":
                return (
                    tool_name,
                    tool_type,
                    DatasetUploader(prefix, api_key, **cfg_tool),
                )
            elif tool_type == "trenddb-fetcher":
                return tool_name, tool_type, TrenddbFetcher(prefix, api_key, **cfg_tool)
            elif tool_type == "services-list":
                return tool_name, tool_type, SeviceListSearcher(prefix, api_key, **cfg_tool)
            elif tool_type == "services-params":
                return tool_name, tool_type, ServiceParamsFetcher(prefix, api_key, **cfg_tool)
            elif tool_type == "services-logs":
                return tool_name, tool_type, ServiceLogger(prefix, api_key, **cfg_tool)
            elif tool_type == "services-reonline":
                return tool_name, tool_type, ServiceReonline(prefix, api_key, **cfg_tool)
            else:
                logger.error(f"未知的工具类型: {tool_type}")

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_map = {
                executor.submit(create_searcher, name, spec): name
                for name, spec in cfg.items()
            }
            for future in as_completed(future_map):
                tool_name = future_map[future]
                try:
                    name, tool_type, searcher = future.result()
                    if searcher:
                        tool_list[name] = searcher
                        self.tool_type_dict.setdefault(tool_type, []).append(name)
                except Exception as e:
                    logger.error(f"加载工具 {tool_name} 失败: {e}")

        self.api_tools.update(tool_list)
        return

    # ==============================
    # 📊 参数解析函数
    # ==============================
    def load_params(self):
        """同步加载并解析参数结构"""
        logger.info("Starting synchronous param parsing")
        try:
            if os.path.exists(self.param_definitions_path):
                cfg = self._read_config()
                self.title = cfg.get("title", self.title)
                logger.success("Loaded title: {}", self.title)
                self._load_params(cfg.get("param-structure", {}))
                self.param_templates = cfg.get("param-template", {})
                self.tab_names = cfg.get("tab-names", {})
                self.patch_info = cfg.get("version-control", {})
            else:
                logger.error(
                    "Configuration file not found: {}", self.param_definitions_path
                )
        except Exception as e:
            logger.exception("Failed to parse parameters")

    def _load_params(self, param_structure: dict):
        """实际参数解析逻辑"""
        self.param_structure = param_structure
        self.init_params = self._recursive_parse(
            param_structure, self.params_type, self.params_default, self.params_options
        )

    def add_binding_model_params(self, param_structure: dict):
        self.model_binding_structure = param_structure
        self.init_params = self._recursive_parse(
            self.model_binding_structure, self.params_type, self.params_default, self.params_options
        )

    def remove_binding_model_params(self):
        self.params_type = {}
        self.params_default = {}
        self.params_options = {}
        self.subchildren_default = {}
        self.model_binding_structure = {}
        self.init_params = self._recursive_parse(
            self.param_structure, self.params_type, self.params_default, self.params_options
        )

    def _recursive_parse(
            self, structure, type_dict, default_dict, options_dict, path_prefix=""
    ):
        result = {}
        for key, node in structure.items():
            full_path = f"{path_prefix}/{key}" if path_prefix else key
            type_dict[full_path] = node.get("type", "unknown")

            if "default" in node:
                default_dict[full_path] = node["default"]
            if "options" in node:
                options_dict[full_path] = node["options"]

            if "children" in node:
                result[key] = self._recursive_parse(
                    node["children"], type_dict, default_dict, options_dict, full_path
                )
            elif "subchildren" in node:
                result[key] = ""
                self.subchildren_default[full_path] = self._recursive_parse(
                    node["subchildren"],
                    type_dict,
                    default_dict,
                    options_dict,
                    full_path,
                )
            else:
                result[key] = node.get("default", "")
        return result

    # ==============================
    # 📦 工具访问接口
    # ==============================
    def get_tools_by_type(self, tool_type: str):
        """根据类型获取工具"""
        return [
            self.api_tools.get(item) for item in self.tool_type_dict.get(tool_type, [])
        ]

    def get_tools_by_path(self, path: str):
        """根据路径获取工具"""
        try:
            return [
                self.api_tools.get(tool_name) for tool_name in self.params_options[path]
            ]
        except Exception as e:
            logger.error(f"获取工具失败: {str(e)}")
            return []

    def get_params_name(self):
        return [
            key
            for key, value in self.param_structure.items()
            if value.get("type") == "subgroup" and "测点名" in value.get("subchildren")
        ]

    def get_upload_name(self, structure=None, path_prefix=""):
        if structure is None:
            structure = self.model_binding_structure
        for key, value in structure.items():
            if value.get("type") == "upload":
                return f"{path_prefix}/{key}"
            elif value.get("children") is not None:
                path = self.get_upload_name(value.get("children"), f"{path_prefix}/{key}" if path_prefix else key)
                if path: return path
        return ""

    def get_model_binding_param_no(self, path):
        names = path.split("/")
        model_name = names[0]
        component_name = names[1]
        param_name = "/".join(names[2:]) if len(names) > 3 else names[2]
        return self.model_binding_structure.get(model_name).get("children").get(component_name).get("children").get(
            param_name).get("id")
