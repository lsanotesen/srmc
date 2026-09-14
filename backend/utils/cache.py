"""
项目树 & 服务列表缓存工具

策略：Cache-Aside + Write-Invalidate
- 读取时先查 Redis，未命中再查 DB 并写回 Redis（TTL 5 分钟）
- 数据变更（增删改项目/子系统/分组/服务）时主动清除缓存
- Redis 不可用时降级直查 DB，不阻塞业务

缓存键：
- projects_tree          : 完整项目树（含子系统、分组），TTL 5 分钟
- services_list:{md5}    : 服务列表分页查询结果，TTL 30 秒
"""
import json
import logging
from typing import Any, Optional, Callable
from utils.redis_client import redis_client

logger = logging.getLogger(__name__)

# 项目树缓存键
PROJECTS_TREE_CACHE_KEY = "projects_tree"
# 缓存 TTL（秒）
PROJECTS_TREE_TTL = 300  # 5 分钟
SERVICES_LIST_TTL = 30   # 30 秒
SERVICES_LIST_PREFIX = "services_list:"


def get_cached(key: str) -> Optional[Any]:
    """从 Redis 读取缓存，失败时返回 None（降级）"""
    try:
        cached = redis_client.get(key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"[cache] Redis 读取失败，降级查库: key={key} err={e}")
    return None


def set_cached(key: str, value: Any, ttl: int) -> None:
    """写入 Redis 缓存，失败时仅记录日志不抛出"""
    try:
        redis_client.setex(key, ttl, json.dumps(value, ensure_ascii=False, default=str))
    except Exception as e:
        logger.warning(f"[cache] Redis 写入失败: key={key} err={e}")


def delete_cached(key: str) -> None:
    """删除 Redis 缓存，失败时仅记录日志"""
    try:
        redis_client.delete(key)
    except Exception as e:
        logger.warning(f"[cache] Redis 删除失败: key={key} err={e}")


def invalidate_projects_tree() -> None:
    """清除项目树缓存（项目/子系统/分组数据变更时调用）"""
    delete_cached(PROJECTS_TREE_CACHE_KEY)
    logger.info("[cache] 项目树缓存已清除")


def invalidate_services_list() -> None:
    """清除所有服务列表缓存（服务增删改时调用）

    使用 SCAN 命令遍历匹配的 key 并删除，避免 KEYS 命令阻塞 Redis。
    """
    try:
        cursor = 0
        deleted_count = 0
        while True:
            cursor, keys = redis_client.scan(
                cursor=cursor, match=f"{SERVICES_LIST_PREFIX}*", count=200
            )
            if keys:
                redis_client.delete(*keys)
                deleted_count += len(keys)
            if cursor == 0:
                break
        if deleted_count > 0:
            logger.info(f"[cache] 服务列表缓存已清除: {deleted_count} 个 key")
    except Exception as e:
        logger.warning(f"[cache] 清除服务列表缓存失败: {e}")


def get_or_set(key: str, ttl: int, loader: Callable[[], Any]) -> Any:
    """Cache-Aside 模式：先查缓存，未命中调用 loader 加载数据并写回缓存"""
    cached = get_cached(key)
    if cached is not None:
        return cached
    data = loader()
    if data is not None:
        set_cached(key, data, ttl)
    return data
