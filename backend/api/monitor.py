import asyncio
import json
import re
import time
import httpx
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from models.service import Service
from models.app_service import AppService
from schemas.monitor import ServiceStatusResponse, BatchStatusResponse
from schemas.common import ResponseModel
from services.monitor_service import get_service_status
from core.database import get_db
from core import monitoring_config
from api.dependencies import require_permission
from api.permission_dependencies import (
    assert_legacy_service_access,
    assert_legacy_services_access,
    assert_server_access,
    filter_legacy_services_query,
)

router = APIRouter()

# Prometheus 数据源统一由 monitoring.conf 提供（见 core/monitoring_config.py）
PROMETHEUS_URL = monitoring_config.get_prometheus_url()
# Node Exporter instance 标签（内置模式 Prometheus 容器内访问宿主机）
NODE_INSTANCE = monitoring_config.get_node_instance()


# PromQL 正则中需转义的特殊字符。
# 注意：正则值先作为 PromQL 字符串字面量解析，反斜杠需写两次（"\\." 才能得到正则 "\\."），
# 因此这里替换为两个反斜杠；也不能用 re.escape（它会把 '-' 转义成 '\-'，PromQL 报未知转义）。
_PROMQL_REGEX_SPECIALS = re.compile(r'([\\.^$*+?()\[\]{}|])')


def _promql_escape(value: str) -> str:
    return _PROMQL_REGEX_SPECIALS.sub(r'\\\\\1', value)


def _resolve_instance_label(server) -> str:
    """按数据源模式解析 Prometheus instance 标签。

    - external：外置 Prometheus 以主机名作为 instance，使用 server.hostname
    - internal：沿用内置 Node Exporter 规则（本机用配置 instance，其余用 ip:9100）
    hostname 为空时返回空串，PromQL 匹配不到数据（返回空结果，不报错）。
    """
    if monitoring_config.get_prometheus_mode() == "external":
        return (server.hostname or "").strip()
    if server.ip in ('127.0.0.1', 'localhost'):
        return NODE_INSTANCE
    return f"{server.ip}:9100"

@router.get("/monitor/status/{service_id}", response_model=ResponseModel)
async def get_service_status_endpoint(service_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    assert_legacy_service_access(db, user, service_id)
    status = get_service_status(service_id)
    return ResponseModel(data={"service_id": service_id, "status": status})

@router.get("/monitor/status", response_model=ResponseModel)
async def get_all_statuses(db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    # 按当前用户数据范围过滤，避免看到其他组织的服务状态
    services = filter_legacy_services_query(db, user, db.query(Service)).all()
    results = []
    running = 0
    stopped = 0
    unknown = 0
    
    for service in services:
        status = get_service_status(service.id)
        results.append({
            "service_id": service.id,
            "service_code": service.service_code,
            "service_name": service.service_name,
            "status": status,
            "ip": service.ip,
            "port": service.port,
            "check_type": service.check_type
        })
        if status == "RUNNING":
            running += 1
        elif status == "STOPPED":
            stopped += 1
        else:
            unknown += 1
    
    return ResponseModel(data={
        "results": results,
        "total": len(services),
        "running": running,
        "stopped": stopped,
        "unknown": unknown
    })

@router.post("/monitor/refresh", response_model=ResponseModel)
async def refresh_all_statuses(db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    # 【已禁用 SSH 状态检测】原先此处调用 update_all_service_statuses() 会通过 SSH
    # 探测服务状态，违反"状态只能由 Agent 上报及心跳判断"的规则，故不再触发。
    # SSH 仅用于启动、停止、远程登录等明确需要 SSH 的操作。
    # 接口与响应格式保持不变，仅返回当前缓存状态。
    return await get_all_statuses(db, user)

@router.post("/monitor/start/{service_id}", response_model=ResponseModel)
async def start_service(service_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_operate"))):
    from services.batch_service import execute_service_operation
    assert_legacy_service_access(db, user, service_id)
    result = await execute_service_operation(service_id, "START", db, user.id, user.username)
    if result["success"]:
        return ResponseModel(data=result)
    return ResponseModel(code=1, message=result["message"], data=result)

@router.post("/monitor/stop/{service_id}", response_model=ResponseModel)
async def stop_service(service_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_operate"))):
    from services.batch_service import execute_service_operation
    assert_legacy_service_access(db, user, service_id)
    result = await execute_service_operation(service_id, "STOP", db, user.id, user.username)
    if result["success"]:
        return ResponseModel(data=result)
    return ResponseModel(code=1, message=result["message"], data=result)

@router.post("/monitor/restart/{service_id}", response_model=ResponseModel)
async def restart_service(service_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_operate"))):
    from services.batch_service import execute_service_operation
    assert_legacy_service_access(db, user, service_id)
    result = await execute_service_operation(service_id, "RESTART", db, user.id, user.username)
    if result["success"]:
        return ResponseModel(data=result)
    return ResponseModel(code=1, message=result["message"], data=result)

@router.post("/monitor/batch/{operation}", response_model=ResponseModel)
async def batch_operation(operation: str, service_ids: list, db: Session = Depends(get_db), user = Depends(require_permission("service_operate"))):
    from services.batch_service import execute_service_operation
    assert_legacy_services_access(db, user, service_ids)
    tasks = [execute_service_operation(sid, operation.upper(), db, user.id, user.username) for sid in service_ids]
    results = await asyncio.gather(*tasks)
    return ResponseModel(data=results)

def _active_alerts_summary(db: Session, user) -> dict:
    """活跃告警汇总（status != RECOVERED）。

    主源为内部告警中心（AlertRecord）；查询异常时明确标记 available=False，
    由前端显示「告警源不可用」，不用 0 伪装为「无告警」。
    """
    from models.alert_record import AlertRecord
    from services.data_scope_service import DataScopeService
    from sqlalchemy import func as _func

    try:
        visible_ids = DataScopeService.get_user_project_ids(db, user)
        query = db.query(AlertRecord)
        if visible_ids is not None:
            query = (query.filter(AlertRecord.project_id.in_(list(visible_ids)))
                     if visible_ids else query.filter(AlertRecord.id < 0))
        open_query = query.filter(AlertRecord.status != "RECOVERED")
        by_severity = {
            sev: int(cnt)
            for sev, cnt in open_query.with_entities(AlertRecord.severity, _func.count(AlertRecord.id))
            .group_by(AlertRecord.severity).all()
        }
        rows = open_query.order_by(AlertRecord.first_seen_at.desc(), AlertRecord.id.desc()).limit(10).all()
        svc_ids = [r.service_id for r in rows if r.service_id]
        name_map = {}
        if svc_ids:
            name_map = {
                sid: name
                for sid, name in db.query(AppService.id, AppService.func_desc)
                .filter(AppService.id.in_(svc_ids)).all()
            }
        items = [{
            "id": r.id,
            "severity": r.severity,
            "status": r.status,
            "title": r.title,
            "content": r.content,
            "ip": r.ip,
            "service_id": r.service_id,
            "service_name": name_map.get(r.service_id) or (f"服务#{r.service_id}" if r.service_id else "-"),
            "first_seen_at": r.first_seen_at.isoformat() if r.first_seen_at else None,
            "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
        } for r in rows]
        return {
            "available": True,
            "source": "internal",
            "open_total": sum(by_severity.values()),
            "by_severity": by_severity,
            "items": items,
        }
    except Exception as e:
        return {
            "available": False,
            "source": "internal",
            "error": f"{type(e).__name__}: {e}",
            "open_total": None,
            "by_severity": {},
            "items": [],
        }


@router.get("/monitor/overview")
async def get_monitor_overview(db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    """监控中心全局概览：服务器健康分布 + 资源风险 TOP5 + 活跃告警。

    统计口径：
    - 分母为当前用户可见的「全部纳管服务器」；
    - 健康/异常依据服务器资源采集结果判定，无监控数据单独统计（不用 0 伪装）；
    - 资源风险阈值取自 monitoring.conf（CPU/内存默认 80%、磁盘默认 90%）；
    - 活跃告警以内部告警中心为主源，不可用时返回 available=False。
    """
    thresholds = monitoring_config.get_thresholds()
    servers = await _collect_server_metrics(db, user)

    total_servers = len(servers)
    data_servers = sum(1 for s in servers if s["has_data"])
    normal = abnormal = 0
    risk_items = []
    for s in servers:
        if not s["has_data"]:
            continue
        metrics = [
            ("cpu", "CPU", s["cpu_percent"], thresholds["cpu"]),
            ("memory", "内存", s["memory_percent"], thresholds["memory"]),
            ("disk", "磁盘", s["disk_usage_percent"], thresholds["disk"]),
        ]
        if any(thr > 0 and val > thr for _, _, val, thr in metrics):
            abnormal += 1
        else:
            normal += 1
        # 取该服务器风险最高的指标：按 值/阈值 归一化比较，使磁盘 90% 与 CPU/内存 80% 可比
        worst = max(metrics, key=lambda m: (m[2] / m[3]) if m[3] else 0)
        risk_items.append({
            "server_id": s["id"],
            "hostname": s["hostname"] or s["ip"],
            "ip": s["ip"],
            "metric": worst[0],
            "metric_label": worst[1],
            "value": worst[2],
            "threshold": worst[3],
            "over_threshold": bool(worst[3] > 0 and worst[2] > worst[3]),
        })

    # 按风险比降序，仅取前 5（有有效数据的服务器不足 5 台时不补零）
    risk_items.sort(key=lambda x: (x["value"] / x["threshold"]) if x["threshold"] else 0, reverse=True)

    return ResponseModel(data={
        "total_servers": total_servers,
        "data_servers": data_servers,
        "normal": normal,
        "abnormal": abnormal,
        "nodata": total_servers - data_servers,
        "resource_risk": abnormal,
        "thresholds": thresholds,
        "top_risk": risk_items[:5],
        "alerts": _active_alerts_summary(db, user),
    })


# ===== 服务器级别监控 API =====

from models.server import Server


async def _collect_server_metrics(db: Session, user) -> list:
    """按当前用户数据范围返回服务器及其 Node Exporter 实时指标。

    复用 api.server 的组织隔离规则（_scope_server_query）；无匹配指标时 has_data=False，
    由前端展示「无数据」，避免用 0 值伪造健康指标。供 /monitor/servers 与 /monitor/overview 共用。
    """
    from api.server import _scope_server_query

    servers = _scope_server_query(db.query(Server), user).all()
    results = []
    # instance 标签 -> 指标字典，如 {"cpu": 12.3, "memory": 45.6, ...}
    by_instance = {}

    server_labels = [_resolve_instance_label(s) for s in servers]
    instances = list(dict.fromkeys(il for il in server_labels if il))

    if instances:
        # 批量查询：所有实例合并为一次正则匹配，5 次请求即可取回全部服务器指标。
        # 原先逐台查询会产生 5×N 个小请求，在共享 Prometheus 上耗时波动极大。
        rx = "|".join(_promql_escape(il) for il in instances)
        node_queries = [
            ("cpu", f'100 - (avg by(instance) (irate(node_cpu_seconds_total{{instance=~"{rx}",mode="idle"}}[5m])) * 100)'),
            ("memory", f'(1 - (node_memory_MemAvailable_bytes{{instance=~"{rx}"}} / node_memory_MemTotal_bytes{{instance=~"{rx}"}})) * 100'),
            ("rx", f'sum by(instance) (rate(node_network_receive_bytes_total{{instance=~"{rx}",device!~"lo|docker.*|veth.*"}}[5m]))'),
            ("tx", f'sum by(instance) (rate(node_network_transmit_bytes_total{{instance=~"{rx}",device!~"lo|docker.*|veth.*"}}[5m]))'),
            ("disk", f'100 - ((node_filesystem_avail_bytes{{instance=~"{rx}",fstype!~"tmpfs|overlay"}} * 100) / node_filesystem_size_bytes{{instance=~"{rx}",fstype!~"tmpfs|overlay"}})'),
        ]

        async with httpx.AsyncClient(timeout=5.0) as client:
            async def _collect(key: str, query: str):
                try:
                    r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                    items = r.json().get('data', {}).get('result') or []
                except Exception:
                    return
                for item in items:
                    il = item.get('metric', {}).get('instance')
                    if not il:
                        continue
                    vals = by_instance.setdefault(il, {})
                    # 同一实例存在多条序列（如多分区）时保留首条，与原先取 result[0] 行为一致
                    if key not in vals:
                        vals[key] = float(item['value'][1])

            await asyncio.gather(*[_collect(k, q) for k, q in node_queries])

    for server, instance_label in zip(servers, server_labels):
        m = by_instance.get(instance_label, {})
        cpu, mem, rx, tx, disk = m.get("cpu"), m.get("memory"), m.get("rx"), m.get("tx"), m.get("disk")
        has_data = bool(m)
        results.append({
            "id": server.id,
            "hostname": server.hostname,
            "ip": server.ip,
            "ssh_port": server.ssh_port,
            "os_type": server.os_type,
            "has_data": has_data,
            "cpu_percent": round(cpu, 2) if cpu is not None else 0.0,
            "memory_percent": round(mem, 2) if mem is not None else 0.0,
            "network_rx_mb": round(rx / 1024 / 1024, 2) if rx is not None else 0.0,
            "network_tx_mb": round(tx / 1024 / 1024, 2) if tx is not None else 0.0,
            "disk_usage_percent": round(disk, 2) if disk is not None else 0.0
        })

    return results


@router.get("/monitor/servers")
async def get_server_list(db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    """获取所有服务器及其实时资源指标"""
    return ResponseModel(data=await _collect_server_metrics(db, user))


@router.get("/monitor/server/{server_id}/metrics")
async def get_server_metrics(
    server_id: int,
    time_range: str = "1h",
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_view"))
):
    """获取单服务器的时间序列指标（CPU/内存/网络）"""
    server = assert_server_access(db, user, server_id)
    
    # 时间范围映射（Prometheus query_range 的 start/end 需为 Unix 时间戳，不支持 now-1h）
    range_seconds = {"1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}
    end_ts = int(time.time())
    start_ts = end_ts - range_seconds.get(time_range, 3600)
    
    metrics = {
        "cpu": [],
        "memory": [],
        "network_rx": [],
        "network_tx": [],
        "disk": []
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        instance_label = _resolve_instance_label(server)
        try:
            # CPU 使用率时间序列
            cpu_query = f'100 - (avg by(instance) (irate(node_cpu_seconds_total{{instance="{instance_label}",mode="idle"}}[5m])) * 100)'
            r = await client.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
                "query": cpu_query,
                "start": start_ts,
                "end": end_ts,
                "step": "1m" if time_range in ["1h", "6h"] else "5m"
            })
            d = r.json()
            if d.get('data',{}).get('result'):
                metrics["cpu"] = [[float(ts), round(float(val), 2)] for ts, val in d['data']['result'][0]['values']]
        except Exception:
            pass
        
        try:
            # 内存使用率时间序列
            mem_query = f'(1 - (node_memory_MemAvailable_bytes{{instance="{instance_label}"}} / node_memory_MemTotal_bytes{{instance="{instance_label}"}})) * 100'
            r = await client.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
                "query": mem_query,
                "start": start_ts,
                "end": end_ts,
                "step": "1m" if time_range in ["1h", "6h"] else "5m"
            })
            d = r.json()
            if d.get('data',{}).get('result'):
                metrics["memory"] = [[float(ts), round(float(val), 2)] for ts, val in d['data']['result'][0]['values']]
        except Exception:
            pass
        
        try:
            # 网络接收速率时间序列
            rx_query = f'sum(rate(node_network_receive_bytes_total{{instance="{instance_label}",device!~"lo|docker.*|veth.*"}}[5m]))'
            r = await client.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
                "query": rx_query,
                "start": start_ts,
                "end": end_ts,
                "step": "1m" if time_range in ["1h", "6h"] else "5m"
            })
            d = r.json()
            if d.get('data',{}).get('result'):
                metrics["network_rx"] = [[float(ts), round(float(val) / 1024 / 1024, 2)] for ts, val in d['data']['result'][0]['values']]
        except Exception:
            pass
        
        try:
            # 网络发送速率时间序列
            tx_query = f'sum(rate(node_network_transmit_bytes_total{{instance="{instance_label}",device!~"lo|docker.*|veth.*"}}[5m]))'
            r = await client.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
                "query": tx_query,
                "start": start_ts,
                "end": end_ts,
                "step": "1m" if time_range in ["1h", "6h"] else "5m"
            })
            d = r.json()
            if d.get('data',{}).get('result'):
                metrics["network_tx"] = [[float(ts), round(float(val) / 1024 / 1024, 2)] for ts, val in d['data']['result'][0]['values']]
        except Exception:
            pass
        
        try:
            # 磁盘使用率时间序列
            disk_query = f'100 - ((node_filesystem_avail_bytes{{instance="{instance_label}",fstype!~"tmpfs|overlay"}} * 100) / node_filesystem_size_bytes{{instance="{instance_label}",fstype!~"tmpfs|overlay"}})'
            r = await client.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
                "query": disk_query,
                "start": start_ts,
                "end": end_ts,
                "step": "1m" if time_range in ["1h", "6h"] else "5m"
            })
            d = r.json()
            if d.get('data',{}).get('result'):
                metrics["disk"] = [[float(ts), round(float(val), 2)] for ts, val in d['data']['result'][0]['values']]
        except Exception:
            pass
    
    return ResponseModel(data=metrics)


@router.get("/monitor/server/{server_id}/services")
async def get_server_services(
    server_id: int,
    time_range: str = "1h",
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_view"))
):
    """获取服务器上所有服务的状态历史"""
    server = assert_server_access(db, user, server_id)
    
    # 获取该服务器上的所有服务（按当前用户数据范围过滤）
    services = filter_legacy_services_query(db, user, db.query(Service).filter(Service.ip == server.ip)).all()
    
    service_status_history = []
    for svc in services:
        status = get_service_status(svc.id)
        service_status_history.append({
            "service_id": svc.id,
            "service_name": svc.service_name or svc.service_code,
            "status": status,
            "check_type": svc.check_type,
            "port": svc.port
        })
    
    # TODO: 从数据库或 Redis 中获取历史状态变化（需要实现状态历史记录功能）
    # 当前返回实时状态，历史数据需要额外的存储机制
    
    return ResponseModel(data={
        "server_ip": server.ip,
        "services": service_status_history,
        "total": len(service_status_history)
    })


@router.get("/monitor/server/{server_id}/processes")
async def get_server_processes(
    server_id: int,
    top_n: int = 10,
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_view"))
):
    """获取服务器上 Top N 进程（按 CPU/内存排序）"""
    server = assert_server_access(db, user, server_id)
    instance_label = _resolve_instance_label(server)
    
    processes = []
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 查询 Top N CPU 进程
            cpu_query = f'topk({top_n}, rate(process_cpu_seconds_total{{instance="{instance_label}"}}[5m]) * 100)'
            r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": cpu_query})
            d = r.json()
            if d.get('data',{}).get('result'):
                for item in d['data']['result']:
                    processes.append({
                        "name": item['metric'].get('comm', 'unknown'),
                        "pid": item['metric'].get('pid', '-'),
                        "cpu_percent": round(float(item['value'][1]), 2),
                        "memory_mb": 0,
                        "type": "cpu_top"
                    })
        except Exception:
            pass
        
        try:
            # 查询 Top N 内存进程
            mem_query = f'topk({top_n}, process_resident_memory_bytes{{instance="{instance_label}"}} / 1024 / 1024)'
            r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": mem_query})
            d = r.json()
            if d.get('data',{}).get('result'):
                for item in d['data']['result']:
                    processes.append({
                        "name": item['metric'].get('comm', 'unknown'),
                        "pid": item['metric'].get('pid', '-'),
                        "cpu_percent": 0,
                        "memory_mb": round(float(item['value'][1]), 2),
                        "type": "memory_top"
                    })
        except Exception:
            pass
    
    return ResponseModel(data={
        "server_ip": server.ip,
        "processes": processes[:top_n * 2]  # 合并后取前 N*2
    })


# ===== 服务器日志查询（Loki，服务器级 Docker 容器日志） =====
# 说明：以 server.ip 精确匹配 Loki 的 source_ip 标签，仅查询该主机日志；
# 无数据时不伪造、不跨主机、不使用 SSH 兜底。

_LOG_RANGE_SECONDS = {"15m": 900, "1h": 3600, "6h": 21600, "24h": 86400}
_LOG_LIMIT_DEFAULT = 200
_LOG_LIMIT_MAX = 1000


def _escape_logql_string(value: str) -> str:
    """转义 LogQL 双引号字符串字面量中的反斜杠与双引号。"""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _extract_log_message(raw: str) -> str:
    """解析采集器写入的 Docker JSON 行（{"log":..,"stream":..,"time":..}）。

    非 JSON（或结构不符）时原样返回，保证任何日志都能展示，不做截断。
    """
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict) and "log" in obj:
            return str(obj.get("log") or "").rstrip("\n")
    except Exception:
        pass
    return (raw or "").rstrip("\n")


@router.get("/monitor/server/{server_id}/logs")
async def get_server_logs(
    server_id: int,
    range: str = "1h",
    container: str = "",
    level: str = "",
    keyword: str = "",
    limit: int = _LOG_LIMIT_DEFAULT,
    db: Session = Depends(get_db),
    user = Depends(require_permission("log_view"))
):
    """按服务器 IP 查询 Loki 中的容器日志。

    返回 data 结构固定为 {enabled, error, containers, logs}：
    - enabled=False：Loki 未启用（url 未配置或 enabled=false）
    - error 非空：查询失败（Loki 不可达或返回异常）
    - logs 为空且无 error：该服务器在所选时间窗内暂无日志
    三者互斥，前端据此区分「未启用 / 暂无日志 / 查询失败」。
    """
    server = assert_server_access(db, user, server_id)

    loki = monitoring_config.get_loki_config()
    if not loki.get("enabled") or not loki.get("url"):
        return ResponseModel(data={"enabled": False, "error": None, "containers": [], "logs": []})

    base = loki["url"].rstrip("/")
    range_key = range if range in _LOG_RANGE_SECONDS else "1h"
    try:
        limit = max(1, min(int(limit), _LOG_LIMIT_MAX))
    except (TypeError, ValueError):
        limit = _LOG_LIMIT_DEFAULT

    ip = (server.ip or "").strip()
    if not ip:
        # 服务器无 IP 时无可匹配的 source_ip，按暂无日志返回
        return ResponseModel(data={"enabled": True, "error": None, "containers": [], "logs": []})

    end_ts = int(time.time())
    start_ts = end_ts - _LOG_RANGE_SECONDS[range_key]
    selector = f'{{source_ip="{_escape_logql_string(ip)}"}}'

    # 日志明细查询：容器（流标签，放入选择器）→ 级别（结构化元数据，走管道）→ 关键词（正则行过滤）
    labels = [f'source_ip="{_escape_logql_string(ip)}"']
    if container:
        labels.append(f'container="{_escape_logql_string(container)}"')
    log_query = "{" + ", ".join(labels) + "}"
    if level:
        log_query += f' | detected_level="{_escape_logql_string(level)}"'
    if keyword:
        log_query += f' |~ "{_escape_logql_string(re.escape(keyword))}"'

    containers = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 容器列表：不受容器/级别/关键词过滤影响，保证下拉框稳定可切回「全部容器」。
        # 使用 count_over_time 聚合查询，只返回标签与计数，不返回日志正文。
        try:
            cr = await client.get(
                f"{base}/loki/api/v1/query",
                params={
                    "query": f'sum by (container) (count_over_time({selector} [{range_key}]))',
                    "time": end_ts,
                },
            )
            for item in (cr.json().get("data", {}).get("result") or []):
                name = (item.get("metric") or {}).get("container")
                if name:
                    containers.append(name)
            containers.sort()
        except Exception:
            containers = []

        # 日志明细查询（query_range 只接受 Unix 时间戳，不支持 now-1h）
        try:
            r = await client.get(
                f"{base}/loki/api/v1/query_range",
                params={
                    "query": log_query,
                    "start": start_ts,
                    "end": end_ts,
                    "limit": limit,
                    "direction": "backward",
                },
            )
            payload = r.json()
            if payload.get("status") != "success":
                raise ValueError(payload.get("message") or "Loki 返回异常")
        except Exception as e:
            return ResponseModel(data={
                "enabled": True, "error": f"{type(e).__name__}: {e}",
                "containers": containers, "logs": []
            })

        logs = []
        for stream in (payload.get("data", {}).get("result") or []):
            labels_ = stream.get("stream") or {}
            lvl = labels_.get("detected_level") or ""
            cont = labels_.get("container") or ""
            for ts_ns, raw in (stream.get("values") or []):
                try:
                    ts = int(ts_ns) // 1_000_000_000
                except (TypeError, ValueError):
                    ts = 0
                logs.append({
                    "timestamp": ts,
                    "level": lvl,
                    "container": cont,
                    "message": _extract_log_message(raw),
                })

    logs.sort(key=lambda x: x["timestamp"], reverse=True)
    return ResponseModel(data={
        "enabled": True, "error": None,
        "containers": containers, "logs": logs[:limit]
    })
