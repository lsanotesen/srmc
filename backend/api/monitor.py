import asyncio
import httpx
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from models.service import Service
from models.app_service import AppService
from schemas.monitor import ServiceStatusResponse, BatchStatusResponse
from schemas.common import ResponseModel
from services.monitor_service import get_service_status, update_all_service_statuses
from core.database import get_db
from api.dependencies import require_permission

router = APIRouter()

PROMETHEUS_URL = "http://srmc-prometheus:9090"
# Node Exporter instance 标签（Prometheus 容器内访问宿主机）
NODE_INSTANCE = "host.docker.internal:9100"

@router.get("/monitor/status/{service_id}", response_model=ResponseModel)
async def get_service_status_endpoint(service_id: int, user = Depends(require_permission("service_view"))):
    status = get_service_status(service_id)
    return ResponseModel(data={"service_id": service_id, "status": status})

@router.get("/monitor/status", response_model=ResponseModel)
async def get_all_statuses(db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    services = db.query(Service).all()
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
    await update_all_service_statuses()
    return await get_all_statuses(db, user)

@router.post("/monitor/start/{service_id}", response_model=ResponseModel)
async def start_service(service_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_operate"))):
    from services.batch_service import execute_service_operation
    result = await execute_service_operation(service_id, "START", db, user.id, user.username)
    if result["success"]:
        return ResponseModel(data=result)
    return ResponseModel(code=1, message=result["message"], data=result)

@router.post("/monitor/stop/{service_id}", response_model=ResponseModel)
async def stop_service(service_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_operate"))):
    from services.batch_service import execute_service_operation
    result = await execute_service_operation(service_id, "STOP", db, user.id, user.username)
    if result["success"]:
        return ResponseModel(data=result)
    return ResponseModel(code=1, message=result["message"], data=result)

@router.post("/monitor/restart/{service_id}", response_model=ResponseModel)
async def restart_service(service_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_operate"))):
    from services.batch_service import execute_service_operation
    result = await execute_service_operation(service_id, "RESTART", db, user.id, user.username)
    if result["success"]:
        return ResponseModel(data=result)
    return ResponseModel(code=1, message=result["message"], data=result)

@router.post("/monitor/batch/{operation}", response_model=ResponseModel)
async def batch_operation(operation: str, service_ids: list, db: Session = Depends(get_db), user = Depends(require_permission("service_operate"))):
    from services.batch_service import execute_service_operation
    tasks = [execute_service_operation(sid, operation.upper(), db, user.id, user.username) for sid in service_ids]
    results = await asyncio.gather(*tasks)
    return ResponseModel(data=results)

@router.get("/monitor/overview")
async def get_monitor_overview(db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    """监控中心概览 - 聚合KPI指标"""
    services = db.query(Service).all()
    running = stopped = unknown = 0
    for svc in services:
        st = get_service_status(svc.id)
        if st == "RUNNING": running += 1
        elif st == "STOPPED": stopped += 1
        else: unknown += 1
    total = len(services)
    health_rate = round(running / total * 100, 1) if total > 0 else 100.0

    # 资源指标（从 Prometheus）
    cpu_values = []
    memory_values = []
    try:
        app_services = db.query(AppService).all()
        async with httpx.AsyncClient(timeout=5.0) as client:
            for svc in app_services:
                try:
                    r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": f'srmc_app_cpu_percent{{app_name="{svc.func_desc}",ip="{svc.ip}",port="{svc.port}"}}'})
                    d = r.json()
                    if d.get('data',{}).get('result'):
                        cpu_values.append(float(d['data']['result'][0]['value'][1]))
                    r2 = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": f'srmc_app_memory_mb{{app_name="{svc.func_desc}",ip="{svc.ip}",port="{svc.port}"}}'})
                    d2 = r2.json()
                    if d2.get('data',{}).get('result'):
                        memory_values.append(float(d2['data']['result'][0]['value'][1]))
                except Exception:
                    pass
    except Exception:
        pass
    avg_cpu = round(sum(cpu_values)/len(cpu_values), 1) if cpu_values else 0
    avg_memory = round(sum(memory_values)/len(memory_values), 1) if memory_values else 0

    # 告警统计
    alert_critical = alert_warning = alert_info = 0
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            ar = await client.get("http://srmc-alertmanager:9093/api/v1/alerts")
            for a in ar.json().get('data', []):
                sev = a.get('labels',{}).get('severity','')
                if sev == 'critical': alert_critical += 1
                elif sev == 'warning': alert_warning += 1
                else: alert_info += 1
    except Exception:
        pass

    return ResponseModel(data={
        "total": total, "running": running, "stopped": stopped, "unknown": unknown,
        "health_rate": health_rate, "avg_cpu": avg_cpu, "avg_memory": avg_memory,
        "active_alerts": alert_critical + alert_warning + alert_info,
        "alert_critical": alert_critical, "alert_warning": alert_warning, "alert_info": alert_info
    })


# ===== 服务器级别监控 API =====

from models.server import Server

@router.get("/monitor/servers")
async def get_server_list(db: Session = Depends(get_db), user = Depends(require_permission("service_view"))):
    """获取所有服务器及其实时资源指标"""
    servers = db.query(Server).all()
    results = []
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for server in servers:
            # 查询 Node Exporter 获取服务器指标
            # 注意：当前 Node Exporter 使用 host 网络模式，instance 为 NODE_INSTANCE
            cpu_percent = 0.0
            memory_percent = 0.0
            network_rx = 0.0
            network_tx = 0.0
            disk_usage = 0.0
            
            # 根据服务器 IP 决定查询的 instance
            # 如果服务器 IP 是 localhost/127.0.0.1，使用 NODE_INSTANCE
            instance_label = NODE_INSTANCE if server.ip in ('127.0.0.1', 'localhost') else f"{server.ip}:9100"
            
            try:
                # CPU 使用率 (1 - idle)
                cpu_query = f'100 - (avg by(instance) (irate(node_cpu_seconds_total{{instance="{instance_label}",mode="idle"}}[5m])) * 100)'
                r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": cpu_query})
                d = r.json()
                if d.get('data',{}).get('result'):
                    cpu_percent = round(float(d['data']['result'][0]['value'][1]), 2)
            except Exception:
                pass
            
            try:
                # 内存使用率
                mem_query = f'(1 - (node_memory_MemAvailable_bytes{{instance="{instance_label}"}} / node_memory_MemTotal_bytes{{instance="{instance_label}"}})) * 100'
                r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": mem_query})
                d = r.json()
                if d.get('data',{}).get('result'):
                    memory_percent = round(float(d['data']['result'][0]['value'][1]), 2)
            except Exception:
                pass
            
            try:
                # 网络接收速率 (bytes/s)
                rx_query = f'sum(rate(node_network_receive_bytes_total{{instance="{instance_label}",device!~"lo|docker.*|veth.*"}}[5m]))'
                r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": rx_query})
                d = r.json()
                if d.get('data',{}).get('result'):
                    network_rx = round(float(d['data']['result'][0]['value'][1]) / 1024 / 1024, 2)  # MB/s
            except Exception:
                pass
            
            try:
                # 网络发送速率 (bytes/s)
                tx_query = f'sum(rate(node_network_transmit_bytes_total{{instance="{instance_label}",device!~"lo|docker.*|veth.*"}}[5m]))'
                r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": tx_query})
                d = r.json()
                if d.get('data',{}).get('result'):
                    network_tx = round(float(d['data']['result'][0]['value'][1]) / 1024 / 1024, 2)  # MB/s
            except Exception:
                pass
            
            try:
                # 磁盘使用率
                disk_query = f'100 - ((node_filesystem_avail_bytes{{instance="{instance_label}",fstype!~"tmpfs|overlay"}} * 100) / node_filesystem_size_bytes{{instance="{instance_label}",fstype!~"tmpfs|overlay"}})'
                r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": disk_query})
                d = r.json()
                if d.get('data',{}).get('result'):
                    disk_usage = round(float(d['data']['result'][0]['value'][1]), 2)
            except Exception:
                pass
            
            results.append({
                "id": server.id,
                "hostname": server.hostname,
                "ip": server.ip,
                "ssh_port": server.ssh_port,
                "os_type": server.os_type,
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "network_rx_mb": network_rx,
                "network_tx_mb": network_tx,
                "disk_usage_percent": disk_usage
            })
    
    return ResponseModel(data=results)


@router.get("/monitor/server/{server_id}/metrics")
async def get_server_metrics(
    server_id: int,
    time_range: str = "1h",
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_view"))
):
    """获取单服务器的时间序列指标（CPU/内存/网络）"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Server not found")
    
    # 时间范围映射
    time_map = {"1h": "1h", "6h": "6h", "24h": "24h", "7d": "7d"}
    tr = time_map.get(time_range, "1h")
    
    metrics = {
        "cpu": [],
        "memory": [],
        "network_rx": [],
        "network_tx": [],
        "disk": []
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        instance_label = NODE_INSTANCE if server.ip in ('127.0.0.1', 'localhost') else f"{server.ip}:9100"
        try:
            # CPU 使用率时间序列
            cpu_query = f'100 - (avg by(instance) (irate(node_cpu_seconds_total{{instance="{instance_label}",mode="idle"}}[5m])) * 100)'
            r = await client.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
                "query": cpu_query,
                "start": f"now-{tr}",
                "end": "now",
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
                "start": f"now-{tr}",
                "end": "now",
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
                "start": f"now-{tr}",
                "end": "now",
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
                "start": f"now-{tr}",
                "end": "now",
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
                "start": f"now-{tr}",
                "end": "now",
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
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Server not found")
    
    # 获取该服务器上的所有服务
    services = db.query(Service).filter(Service.ip == server.ip).all()
    
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
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Server not found")
    
    processes = []
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 查询 Top N CPU 进程
            cpu_query = f'topk({top_n}, rate(process_cpu_seconds_total{{instance="{server.ip}:9100"}}[5m]) * 100)'
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
            mem_query = f'topk({top_n}, process_resident_memory_bytes{{instance="{server.ip}:9100"}} / 1024 / 1024)'
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
