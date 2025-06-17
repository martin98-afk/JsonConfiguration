import os.path
import shutil
import yaml

from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtCore import QObject, pyqtSignal, QThreadPool

from application.tools.file_uploader import DatasetUploader
from application.tools.point_search import PointSearcher
from application.tools.rtsp_search import RTSPSearcher
from application.tools.service_logger import ServiceLogger
from application.tools.service_params import ServiceParamsFetcher
from application.tools.service_reonline import ServiceReonline
from application.tools.services_search import SeviceListSearcher

from application.tools.trenddb_fectcher import TrenddbFetcher
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
        self.param_structure = {}
        self.init_params = {}
        self.params_type = {}
        self.params_default = {}
        self.params_options = {}
        self.subchildren_default = {}
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
        logger.info("Launching asynchronous tools load")
        worker = Worker(self.load_tools)
        worker.signals.finished.connect(
            lambda _: (logger.info("Tools async load finished"))
        )
        worker.signals.error.connect(
            lambda err: logger.error("Async full load error: {}", err)
        )
        self.threadpool.start(worker)

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
    def load_tools(self):
        """同步加载 API 工具"""
        logger.info("Starting synchronous tool load")
        try:
            if os.path.exists(self.param_definitions_path):
                cfg = self._read_config()
                self._load_tools(cfg.get("api-search", cfg.get("api-tools", {})))
            else:
                logger.error(
                    "Configuration file not found: {}", self.param_definitions_path
                )
        except Exception as e:
            logger.exception("Failed to load tools")

    def _load_tools(self, tools_config: dict):
        """实际加载工具的逻辑"""
        self.api_tools = self._load_tools_parallel(tools_config)

    def _load_tools_parallel(self, cfg: dict) -> dict:
        """并行加载工具实例"""
        logger.debug("Parallel tool load started for tools: {}", list(cfg.keys()))
        tool_list = {}
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

        with ThreadPoolExecutor(max_workers=min(len(cfg), 10)) as executor:
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
        return tool_list

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
