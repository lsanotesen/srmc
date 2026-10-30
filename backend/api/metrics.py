"""Prometheus指标API"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CollectorRegistry, Counter, Gauge
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Any
import httpx
import asyncio

from core.database import get_db
from core import monitoring_config
from models.app_service import AppService
from utils.crypto import decrypt
from api.dependencies import get_current_user

router = APIRouter()

# Prometheus / Alertmanager 数据源统一由 monitoring.conf 提供（见 core/monitoring_config.py）
PROMETHEUS_URL = monitoring_config.get_prometheus_url()
ALERTMANAGER_URL = monitoring_config.get_alertmanager_url()

# Prometheus指标
service_count = Gauge('srmc_service_count', 'Total number of services', ['project', 'deploy_type', 'status'])
service_status = Gauge('srmc_service_status', 'Service status (1=running, 0=stopped)', ['service_id', 'service_name', 'ip'])

async def query_prometheus(query: str) -> Dict[str, Any]:
    """查询Prometheus"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"查询Prometheus失败: {e}")
        return {"data": {"result": []}}

@router.get("/metrics", response_class=PlainTextResponse)
async def get_metrics(db: Session = Depends(get_db)):
    """暴露Prometheus指标"""
    # 更新服务数量指标
    services = db.query(AppService).all()
    for service in services:
        service_count.labels(
            project=service.project_id,
            deploy_type=service.deploy_type or 'HOST',
            status='UNKNOWN'
        ).set(1)
    
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")

@router.get("/api/services/prometheus/status")
async def get_services_status_via_prometheus(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """通过Prometheus获取服务状态"""
    services = db.query(AppService).all()
    results = []
    
    for service in services:
        status = await check_service_via_prometheus(service)
        results.append({
            "service_id": service.id,
            "name": service.func_desc,
            "ip": service.ip,
            "port": service.port,
            "status": status,
            "deploy_type": service.deploy_type
        })
    
    return {"code": 0, "data": results}

async def check_service_via_prometheus(service: AppService) -> str:
    """通过Prometheus检查服务状态"""
    try:
        # 查询应用状态
        query = f'srmc_app_status{{app_name="{service.func_desc}",ip="{service.ip}",port="{service.port}"}}'
        result = await query_prometheus(query)
        
        if result.get('data', {}).get('result'):
            status_value = result['data']['result'][0].get('value', [0, '0'])[1]
            return "RUNNING" if float(status_value) == 1 else "STOPPED"
        
        # 如果没有找到应用指标，尝试查询Docker容器状态
        if service.deploy_type == 'DOCKER' and service.container_name:
            query = f'srmc_docker_container_status{{container_name="{service.container_name}",ip="{service.ip}"}}'
            result = await query_prometheus(query)
            
            if result.get('data', {}).get('result'):
                status_value = result['data']['result'][0].get('value', [0, '0'])[1]
                return "RUNNING" if float(status_value) == 1 else "STOPPED"
        
        return "UNKNOWN"
    except Exception as e:
        print(f"检查服务状态失败: {e}")
        return "UNKNOWN"

@router.post("/api/alerts/webhook")
async def alert_webhook(
    data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """接收Alertmanager告警Webhook"""
    try:
        # 处理告警数据
        alerts = data.get('alerts', [])
        for alert in alerts:
            status = alert.get('status')
            labels = alert.get('labels', {})
            annotations = alert.get('annotations', {})
            
            # 记录告警到数据库或发送通知
            print(f"收到告警: {status} - {labels.get('alertname')}")
        
        return {"code": 0, "message": "告警已接收"}
    except Exception as e:
        return {"code": 500, "message": f"处理告警失败: {str(e)}"}

@router.get("/api/metrics/services")
async def get_service_metrics(
    service_id: int = None,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """获取服务指标"""
    if service_id:
        service = db.query(AppService).filter(AppService.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="服务不存在")

        metrics = (await fetch_service_metrics([service]))[0]
        return {"code": 0, "data": metrics}

    # 获取所有服务指标
    services = db.query(AppService).all()
    return {"code": 0, "data": await fetch_service_metrics(services)}


async def fetch_service_metrics(services: List[AppService]) -> List[Dict[str, Any]]:
    """批量获取服务指标。

    按指标名整体查询一次，再按 (app_name, ip, port) 与传入服务匹配；
    避免每个服务发 4 个小请求，服务多时接口耗时线性增长。
    """
    async def _index_by_key(metric: str) -> Dict[tuple, str]:
        result = await query_prometheus(metric)
        index = {}
        for item in result.get('data', {}).get('result') or []:
            m = item.get('metric', {})
            index.setdefault((m.get('app_name'), m.get('ip'), m.get('port')), item.get('value', [0, '0'])[1])
        return index

    status_idx, memory_idx, cpu_idx, uptime_idx = await asyncio.gather(
        _index_by_key('srmc_app_status'),
        _index_by_key('srmc_app_memory_mb'),
        _index_by_key('srmc_app_cpu_percent'),
        _index_by_key('srmc_app_uptime_seconds'),
    )

    results = []
    for service in services:
        key = (service.func_desc, str(service.ip), str(service.port))
        status = "UNKNOWN"
        memory_mb = 0
        cpu_percent = 0
        uptime_seconds = 0

        if key in status_idx:
            status = "RUNNING" if float(status_idx[key]) == 1 else "STOPPED"
        if key in memory_idx:
            memory_mb = float(memory_idx[key])
        if key in cpu_idx:
            cpu_percent = float(cpu_idx[key])
        if key in uptime_idx:
            uptime_seconds = float(uptime_idx[key])

        results.append({
            "service_id": service.id,
            "name": service.func_desc,
            "ip": service.ip,
            "port": service.port,
            "status": status,
            "memory_mb": memory_mb,
            "cpu_percent": cpu_percent,
            "uptime_seconds": uptime_seconds,
            "deploy_type": service.deploy_type
        })
    return results

@router.get("/api/alerts")
async def get_alerts(user = Depends(get_current_user)):
    """获取告警列表"""
    # 未配置 Alertmanager（如外置模式）时返回空结果
    if not ALERTMANAGER_URL:
        return {"code": 0, "data": []}
    try:
        # 查询Alertmanager的告警
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{ALERTMANAGER_URL}/api/v1/alerts")
            response.raise_for_status()
            data = response.json()
            
            # 格式化告警数据
            alerts = []
            for alert in data.get('data', []):
                alerts.append({
                    "alertname": alert.get('labels', {}).get('alertname'),
                    "instance": alert.get('labels', {}).get('instance'),
                    "severity": alert.get('labels', {}).get('severity'),
                    "summary": alert.get('annotations', {}).get('summary'),
                    "description": alert.get('annotations', {}).get('description'),
                    "startsAt": alert.get('startsAt'),
                    "endsAt": alert.get('endsAt'),
                    "status": alert.get('status')
                })
            
            return {"code": 0, "data": alerts}
    except Exception as e:
        print(f"获取告警失败: {e}")
        return {"code": 500, "message": f"获取告警失败: {str(e)}", "data": []}