"""SRMC 监控数据源配置加载器（独立于业务代码）

从 INI 格式的 monitoring.conf 读取 Prometheus / Alertmanager / Loki 配置：
- 配置文件由 Docker Compose 挂载，真实环境地址不写入业务代码；
- Prometheus 按 mode（external/internal）统一选择数据源，前端不参与切换；
- 文件缺失或解析失败时回退到内置默认值，保持现有部署行为兼容。
"""
import configparser
import os
from typing import Optional

# 配置文件路径：优先环境变量 MONITORING_CONFIG_FILE，其次容器内挂载路径，
# 最后回退到仓库根目录（便于容器外直接运行后端调试）。
_ENV_PATH = os.environ.get("MONITORING_CONFIG_FILE", "")
_REPO_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "monitoring.conf"))
_CONTAINER_PATH = "/app/monitoring.conf"

# 内置默认值（与历史行为一致，不含任何外置部署地址）
_DEFAULT_PROMETHEUS_MODE = "internal"
_DEFAULT_PROMETHEUS_INTERNAL_URL = "http://srmc-prometheus:9090"
_DEFAULT_PROMETHEUS_INTERNAL_NODE_INSTANCE = "host.docker.internal:9100"
_DEFAULT_ALERTMANAGER_URL = "http://srmc-alertmanager:9093"


def _resolve_path() -> str:
    if _ENV_PATH:
        return _ENV_PATH
    for path in (_CONTAINER_PATH, _REPO_ROOT_PATH):
        if os.path.isfile(path):
            return path
    return _CONTAINER_PATH


def _load() -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(_resolve_path(), encoding="utf-8")
    except Exception:
        # 配置不可读（缺失/目录/权限）时保持空解析器，回退默认值
        pass
    return parser


_parser = _load()


def _get(section: str, option: str, default: str = "") -> str:
    try:
        value = _parser.get(section, option)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return default
    return (value or "").strip()


def get_prometheus_mode() -> str:
    """数据源模式：external | internal（非法值一律按 internal 处理）。"""
    return "external" if _get("prometheus", "mode", _DEFAULT_PROMETHEUS_MODE).lower() == "external" else "internal"


def get_prometheus_url() -> str:
    """按模式统一选择 Prometheus 数据源地址。"""
    if get_prometheus_mode() == "external":
        return _get("prometheus", "external_url", "") or _get("prometheus", "internal_url", _DEFAULT_PROMETHEUS_INTERNAL_URL)
    return _get("prometheus", "internal_url", _DEFAULT_PROMETHEUS_INTERNAL_URL)


def get_node_instance() -> str:
    """内置模式 Node Exporter instance 标签（宿主机，host 网络模式）。"""
    return _get("prometheus", "internal_node_instance", _DEFAULT_PROMETHEUS_INTERNAL_NODE_INSTANCE)


def get_alertmanager_url() -> Optional[str]:
    """Alertmanager 地址；未配置时返回 None，调用方跳过实时告警查询。"""
    return _get("alertmanager", "url", _DEFAULT_ALERTMANAGER_URL) or None


def get_loki_config() -> dict:
    """Loki 日志查询配置；enabled 为假或 url 为空时由调用方按「未启用」处理。"""
    return {
        "enabled": _get("loki", "enabled", "false").lower() == "true",
        "url": _get("loki", "url", ""),
    }


def _get_float(section: str, option: str, default: float) -> float:
    try:
        return float(_get(section, option, str(default)))
    except (TypeError, ValueError):
        return default


def get_thresholds() -> dict:
    """资源风险阈值（百分比）。CPU/内存默认 80，磁盘默认 90；非法值回退默认。"""
    return {
        "cpu": _get_float("thresholds", "cpu", 80.0),
        "memory": _get_float("thresholds", "memory", 80.0),
        "disk": _get_float("thresholds", "disk", 90.0),
    }
