"""
运行总览 Dashboard API

提供 4 个只读接口，为前端运行总览页提供数据：
- overview       6 张统计卡片（项目数/服务数/运行中/已停止/Agent异常/状态未知）
- projects       按项目聚合的运行状态
- stopped-services 当前停止服务列表（分页）
- agent-offline  Agent 异常服务列表

所有查询经过 DataScopeService 权限过滤，普通用户只能看到有权限的项目数据。
服务状态不在 DB 中，从 Redis service_status:{id} 批量 MGET 获取。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta

from core.database import get_db
from api.dependencies import get_current_user, require_permission
from schemas.common import ResponseModel
from models.app_service import AppService
from models.project import Project
from models.agent import Agent
from services.data_scope_service import DataScopeService

router = APIRouter()

# 异常态（不等于"未知"）：FAILED/PARTIAL 等需要单独统计，避免被误报为状态未知
ABNORMAL_STATUSES = {"FAILED", "PARTIAL", "STARTING", "STOPPING", "RESTARTING", "UNHEALTHY", "ERROR"}


def _classify_status(status: str, missing: bool) -> str:
    """把服务状态归类为 running/stopped/inactive/abnormal/unknown 五个桶。

    只有"取不到状态"或状态本身为 UNKNOWN 才算 unknown；
    FAILED/PARTIAL 等属于异常，单独统计。
    """
    if missing or not status or status == "UNKNOWN":
        return "unknown"
    if status == "RUNNING":
        return "running"
    if status == "STOPPED":
        return "stopped"
    if status in ("INACTIVE", "COMPLETED"):
        return "inactive"
    if status in ABNORMAL_STATUSES:
        return "abnormal"
    return "unknown"


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------

def _get_visible_services(db: Session, user) -> list[AppService]:
    """获取当前用户可见的所有 AppService（经过 DataScope 权限过滤）"""
    query = db.query(AppService)
    if not DataScopeService._is_super_admin(user):
        visible_pids = DataScopeService.get_user_project_ids(db, user)
        query = query.filter(AppService.project_id.in_(visible_pids))
    return query.all()


def _bulk_fetch_status(db: Session, service_ids: list[int]) -> dict[int, dict]:
    """
    从 Redis 批量获取服务运行状态。

    返回: {service_id: {"status": str, "source": str}}
    status 可能值: RUNNING / STOPPED / PARTIAL(仅前端聚合) / UNKNOWN
    """
    result: dict[int, dict] = {}
    if not service_ids:
        return result

    try:
        from utils.redis_client import redis_client
        status_keys = [f"service_status:{sid}" for sid in service_ids]
        source_keys = [f"service_status_source:{sid}" for sid in service_ids]
        status_vals = redis_client.mget(status_keys)
        source_vals = redis_client.mget(source_keys)

        for i, sid in enumerate(service_ids):
            raw_s = status_vals[i]
            status_str = (raw_s.decode() if raw_s and isinstance(raw_s, bytes) else (raw_s or "UNKNOWN")).upper()
            raw_src = source_vals[i]
            source_str = raw_src.decode() if raw_src and isinstance(raw_src, bytes) else (raw_src or "")
            result[sid] = {"status": status_str, "source": source_str, "missing": raw_s is None}
    except Exception as e:
        print(f"[dashboard] Redis status lookup failed: {e}")
        for sid in service_ids:
            result[sid] = {"status": "UNKNOWN", "source": "", "missing": True}

    return result


def _agent_is_online(agent: Optional[Agent]) -> bool:
    """Agent 在线判断：复用 agent.py 的软/硬在线逻辑。
    硬在线 = WS 连接存在；软在线 = 最近 30s 内心跳。
    此处只能判断软在线（DB last_heartbeat），硬在线需查 WS manager。
    """
    if agent is None:
        return False
    # 先试硬在线（需要已导入 manager）
    try:
        from api.agent import manager
        if manager.is_online(agent.uuid):
            return True
    except Exception:
        pass
    # 回退软在线
    if agent.last_heartbeat:
        return datetime.now() - agent.last_heartbeat < timedelta(seconds=30)
    return False


# ---------------------------------------------------------------------------
# 7 张统计卡片
# ---------------------------------------------------------------------------

@router.get("/dashboard/overview", response_model=ResponseModel)
async def dashboard_overview(
    db: Session = Depends(get_db),
    user=Depends(require_permission("service_view")),
):
    """全局统计概览：7 张卡片"""
    services = _get_visible_services(db, user)
    project_ids = {s.project_id for s in services}

    # 项目数
    project_count = db.query(Project).filter(Project.id.in_(project_ids)).count() if project_ids else 0

    # Redis 批量取状态
    status_map = _bulk_fetch_status(db, [s.id for s in services])

    # Agent 在线判断（用 Agent 表 + last_heartbeat）
    agent_uuids = {s.agent_uuid for s in services if s.agent_uuid}
    agents = {}
    if agent_uuids:
        for a in db.query(Agent).filter(Agent.uuid.in_(agent_uuids)).all():
            agents[a.uuid] = a

    running = stopped = unknown = inactive = abnormal = 0
    agent_offline_count = 0

    for svc in services:
        info = status_map.get(svc.id, {})
        st = info.get("status", "UNKNOWN").upper()
        bucket = _classify_status(st, info.get("missing", False))

        if bucket == "running":
            running += 1
        elif bucket == "stopped":
            stopped += 1
        elif bucket == "inactive":
            inactive += 1
        elif bucket == "abnormal":
            abnormal += 1
        else:
            unknown += 1

        # Agent 异常：有 agent_uuid 但 Agent 离线
        if svc.agent_uuid:
            agent = agents.get(svc.agent_uuid)
            if not _agent_is_online(agent):
                agent_offline_count += 1

    return ResponseModel(data={
        "projectCount": project_count,
        "serviceCount": len(services),
        "runningCount": running,
        "stoppedCount": stopped,
        "inactiveCount": inactive,
        "abnormalCount": abnormal,
        "agentOfflineCount": agent_offline_count,
        "unknownCount": unknown,
    })


# ---------------------------------------------------------------------------
# 项目聚合统计
# ---------------------------------------------------------------------------

@router.get("/dashboard/projects", response_model=ResponseModel)
async def dashboard_projects(
    db: Session = Depends(get_db),
    user=Depends(require_permission("service_view")),
):
    """按项目聚合运行状态"""
    services = _get_visible_services(db, user)

    # 取所有相关项目
    project_ids = {s.project_id for s in services}
    projects = {}
    if project_ids:
        for p in db.query(Project).filter(Project.id.in_(project_ids)).all():
            projects[p.id] = p

    # Redis 批量取状态
    status_map = _bulk_fetch_status(db, [s.id for s in services])

    # Agent 字典
    agent_uuids = {s.agent_uuid for s in services if s.agent_uuid}
    agents = {}
    if agent_uuids:
        for a in db.query(Agent).filter(Agent.uuid.in_(agent_uuids)).all():
            agents[a.uuid] = a

    # 按项目分组统计
    project_stats: dict[int, dict] = {}
    for svc in services:
        pid = svc.project_id
        if pid not in project_stats:
            project_stats[pid] = {
                "projectId": pid,
                "projectName": projects[pid].name if pid in projects else f"项目#{pid}",
                "serviceCount": 0,
                "runningCount": 0,
                "stoppedCount": 0,
                "inactiveCount": 0,
                "abnormalCount": 0,
                "agentOfflineCount": 0,
                "unknownCount": 0,
            }
        ps = project_stats[pid]
        ps["serviceCount"] += 1

        info = status_map.get(svc.id, {})
        bucket = _classify_status(info.get("status", "UNKNOWN").upper(), info.get("missing", False))
        if bucket == "running":
            ps["runningCount"] += 1
        elif bucket == "stopped":
            ps["stoppedCount"] += 1
        elif bucket == "inactive":
            ps["inactiveCount"] += 1
        elif bucket == "abnormal":
            ps["abnormalCount"] += 1
        else:
            ps["unknownCount"] += 1

        if svc.agent_uuid:
            agent = agents.get(svc.agent_uuid)
            if not _agent_is_online(agent):
                ps["agentOfflineCount"] += 1

    # 计算健康状态
    for ps in project_stats.values():
        if ps["stoppedCount"] > 0 or ps["abnormalCount"] > 0:
            ps["healthStatus"] = "异常"
        elif ps["agentOfflineCount"] > 0:
            ps["healthStatus"] = "Agent异常"
        elif ps["unknownCount"] > 0:
            ps["healthStatus"] = "状态未知"
        else:
            ps["healthStatus"] = "正常"

    # 按健康状态排序（异常优先）
    health_order = {"异常": 0, "Agent异常": 1, "状态未知": 2, "正常": 3}
    result = sorted(project_stats.values(), key=lambda x: health_order.get(x["healthStatus"], 9))
    return ResponseModel(data=result)


# ---------------------------------------------------------------------------
# 停止服务列表（分页）
# ---------------------------------------------------------------------------

@router.get("/dashboard/stopped-services", response_model=ResponseModel)
async def dashboard_stopped_services(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(require_permission("service_view")),
):
    """当前停止服务列表，支持分页"""
    services = _get_visible_services(db, user)
    if not services:
        return ResponseModel(data={"items": [], "total": 0, "page": page, "size": size})

    # Redis 批量取状态
    status_map = _bulk_fetch_status(db, [s.id for s in services])

    # 项目字典
    project_ids = {s.project_id for s in services}
    projects = {}
    if project_ids:
        for p in db.query(Project).filter(Project.id.in_(project_ids)).all():
            projects[p.id] = p

    # 子系统字典
    from models.subsystem import Subsystem
    sub_ids = {s.subsystem_id for s in services if s.subsystem_id}
    subsystems = {}
    if sub_ids:
        for sub in db.query(Subsystem).filter(Subsystem.id.in_(sub_ids)).all():
            subsystems[sub.id] = sub

    # Redis 批量取最后更新时间（用 service_status 写入时间）
    # Redis 没有原生 TTL 剩余时间查询，但可以用 `TTL` 命令推断
    # 更准确做法：Agent 心跳时写入 last_update 字段。暂用 status_source 写入时间近似。
    # 简化：用 Redis TTL 反推，或直接返回 Agent last_heartbeat
    from utils.redis_client import redis_client

    stopped_services = []
    for svc in services:
        st_info = status_map.get(svc.id, {})
        st = st_info.get("status", "UNKNOWN").upper()
        if st != "STOPPED":
            continue

        # 查 Redis 剩余 TTL 估算最后更新时间
        last_update = None
        try:
            ttl = redis_client.ttl(f"service_status:{svc.id}")
            if ttl and ttl > 0:
                # TTL 60s → 假设最后更新时间 = now - (60 - ttl)
                last_update = (datetime.now() - timedelta(seconds=60 - ttl)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

        stopped_services.append({
            "id": svc.id,
            "project_id": svc.project_id,
            "subsystem_id": svc.subsystem_id,
            "func_desc": svc.func_desc,
            "project_name": projects.get(svc.project_id, Project).name if projects.get(svc.project_id) else None,
            "subsystem_name": subsystems.get(svc.subsystem_id, Subsystem).subsystem_name if subsystems.get(svc.subsystem_id) else None,
            "ip": svc.ip,
            "deploy_type": svc.deploy_type,
            "agent_uuid": svc.agent_uuid,
            "agent_status": "在线" if st_info.get("source") == "AGENT" else ("离线" if st_info.get("source") == "OFFLINE" else "未知"),
            "status": st,
            "last_update": last_update,
        })

    total = len(stopped_services)
    start = (page - 1) * size
    items = stopped_services[start:start + size]

    return ResponseModel(data={"items": items, "total": total, "page": page, "size": size})


# ---------------------------------------------------------------------------
# Agent 异常服务列表
# ---------------------------------------------------------------------------

@router.get("/dashboard/agent-offline", response_model=ResponseModel)
async def dashboard_agent_offline(
    db: Session = Depends(get_db),
    user=Depends(require_permission("service_view")),
):
    """Agent 异常服务列表（Agent 离线 或 status_source=OFFLINE）"""
    services = _get_visible_services(db, user)

    # 只看有关联 agent_uuid 的
    services_with_agent = [s for s in services if s.agent_uuid]
    if not services_with_agent:
        return ResponseModel(data={"items": [], "total": 0})

    # Redis 批量取状态
    status_map = _bulk_fetch_status(db, [s.id for s in services_with_agent])

    # Agent 字典
    agent_uuids = {s.agent_uuid for s in services_with_agent}
    agents = {}
    if agent_uuids:
        for a in db.query(Agent).filter(Agent.uuid.in_(agent_uuids)).all():
            agents[a.uuid] = a

    # 项目字典
    project_ids = {s.project_id for s in services_with_agent}
    projects = {}
    if project_ids:
        for p in db.query(Project).filter(Project.id.in_(project_ids)).all():
            projects[p.id] = p

    offline_items = []
    for svc in services_with_agent:
        agent = agents.get(svc.agent_uuid)
        st_info = status_map.get(svc.id, {})
        source = st_info.get("source", "")

        is_offline = (source == "OFFLINE") or (not _agent_is_online(agent))
        if not is_offline:
            continue

        offline_items.append({
            "id": svc.id,
            "project_id": svc.project_id,
            "func_desc": svc.func_desc,
            "project_name": projects.get(svc.project_id).name if svc.project_id in projects else None,
            "ip": svc.ip,
            "agent_uuid": svc.agent_uuid,
            "agent_status": "离线",
            "last_heartbeat": agent.last_heartbeat.strftime("%Y-%m-%d %H:%M:%S") if agent and agent.last_heartbeat else None,
            "last_update": agent.updated_at.strftime("%Y-%m-%d %H:%M:%S") if agent and agent.updated_at else None,
        })

    return ResponseModel(data={"items": offline_items, "total": len(offline_items)})
