"""版本号归一化：系统内部统一使用不带前缀的规范形态（如 1.0.1），展示时再由前端加 v 前缀。

写入 Agent config.yaml 的 deploy.version、更新任务的版本比对，都必须先归一化，
否则 "V1.0.1" 与 "v1.0.1" 这类大小写/前缀差异会导致版本比对失配。
"""
import re

_PREFIX_RE = re.compile(r"^[vV](?=\d)")


def normalize_version(value: str | None) -> str:
    """去掉首尾空白与前缀 v/V，返回规范版本号。

    仅当 v/V 后面紧跟数字时才视为版本前缀，避免误伤 "variant" 这类正常取值。
    """
    if not value:
        return ""
    return _PREFIX_RE.sub("", value.strip())
