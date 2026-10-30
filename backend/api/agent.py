from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, Query, Header, Body
from fastapi.websockets import WebSocketState
from sqlalchemy.orm import Session
from sqlalchemy import func
from starlette.websockets import WebSocket as StarletteWebSocket
from core.database import get_db
from models.agent import Agent
from models.app_service import AppService
from models.service_container_config import ServiceContainerConfig
from schemas.common import ResponseModel
from utils.redis_client import redis_client
from utils.ssh_pool import ssh_pool
from core.config import settings
from api.dependencies import get_current_user, require_permission
import services.container_status_service as container_status_service
import services.alert_service as alert_service
import json
import asyncio
from datetime import datetime
import uuid
import time

router = APIRouter()

class AgentConnectionManager:
    def __init__(self):
        self.active_connections = {}
        self.pending_requests = {}
        self.log_subscribers = {}
    
    async def connect(self, websocket: WebSocket, agent_uuid: str):
        await websocket.accept()
        # 同一 Agent 重连：关闭并替换旧连接，避免旧 readLoop 残留在断开时误删新连接
        old = self.active_connections.get(agent_uuid)
        if old is not None and old is not websocket:
            try:
                await old.close()
            except Exception:
                pass
        self.active_connections[agent_uuid] = websocket

    def disconnect(self, agent_uuid: str, websocket: WebSocket = None) -> bool:
        cur = self.active_connections.get(agent_uuid)
        # 仅当字典里注册的就是传入的这条连接时才移除；
        # 旧连接延迟断开时不能把重连后的新连接误删（websocket=None 表示强制移除，如删除 Agent）
        if websocket is None or cur is websocket:
            self.active_connections.pop(agent_uuid, None)
            return True
        return False
    
    async def send_message(self, agent_uuid: str, message: dict):
        if agent_uuid in self.active_connections:
            try:
                await self.active_connections[agent_uuid].send_json(message)
                return True
            except Exception as e:
                print(f"Send message failed: {e}")
                return False
        return False
    
    def is_online(self, agent_uuid: str, last_heartbeat=None) -> bool:
        # 硬在线：WebSocket 连接存在
        if agent_uuid in self.active_connections:
            return True
        # 软在线：WebSocket 暂时断开（重连中），但最近 30 秒内有心跳
        if last_heartbeat:
            from datetime import timedelta
            if datetime.now() - last_heartbeat < timedelta(seconds=30):
                return True
        return False
    
    async def send_command_with_response(self, agent_uuid: str, service_id: str, action: str, service: AppService, timeout: int = 30):
        request_id = str(uuid.uuid4())
        
        # 构建完整的命令路径
        program_path = service.program_path or ""
        start_cmd = f"{program_path}/{service.start_script}" if service.start_script else ""
        stop_cmd = f"{program_path}/{service.stop_script}" if service.stop_script else ""
        
        # 重启命令：不拼接复合命令，让 Agent 自动走 stop → start 流程
        # 因为 Agent 的 expandCmdAndWorkDir 只能处理单个脚本路径
        restart_cmd = ""
        
        # 将后端的部署类型转换为Agent可识别的类型
        deploy_type_map = {
            "HOST": "PROCESS",
            "HOST_APP": "PROCESS",
            "DOCKER": "DOCKER",
            "DOCKER_COMPOSE": "DOCKER_COMPOSE",
            "PROCESS": "PROCESS",
        }
        agent_deploy_type = deploy_type_map.get(service.deploy_type, "PROCESS")
        
        message = {
            "type": "command",
            "request_id": request_id,
            "timestamp": datetime.now().timestamp(),
            "data": {
                "service_id": service_id,
                "action": action,
                "username": service.username or "",
                "deploy_type": agent_deploy_type,
                "docker_name": service.container_name or "",
                "compose_path": service.program_path or "",
                "program_path": service.program_path or "",
                "start_cmd": start_cmd,
                "stop_cmd": stop_cmd,
                "restart_cmd": restart_cmd,
                "log_path": service.log_path or "",
            }
        }
        
        print(f"[Agent Cmd] Sending to {agent_uuid}: action={action}, deploy_type={agent_deploy_type}, start_cmd={start_cmd}, stop_cmd={stop_cmd}, username={service.username}")
        print(f"[Agent Cmd] Full message: {message}")
        
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        try:
            sent = await self.send_message(agent_uuid, message)
            if not sent:
                raise Exception("Agent not connected")
            
            done, _ = await asyncio.wait([future], timeout=timeout)
            if done:
                return future.result()
            else:
                raise asyncio.TimeoutError(f"Command timeout after {timeout}s")
        finally:
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
    
    def resolve_pending_request(self, request_id: str, result: dict):
        if request_id in self.pending_requests:
            self.pending_requests[request_id].set_result(result)
    
    def subscribe_log(self, service_id: str, websocket: WebSocket):
        if service_id not in self.log_subscribers:
            self.log_subscribers[service_id] = []
        self.log_subscribers[service_id].append(websocket)
    
    def unsubscribe_log(self, service_id: str, websocket: WebSocket):
        if service_id in self.log_subscribers:
            self.log_subscribers[service_id].remove(websocket)
            if not self.log_subscribers[service_id]:
                del self.log_subscribers[service_id]
    
    async def broadcast_log(self, service_id: str, message: dict):
        if service_id in self.log_subscribers:
            for websocket in self.log_subscribers[service_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    print(f"Broadcast log failed: {e}")
                    self.unsubscribe_log(service_id, websocket)

manager = AgentConnectionManager()

@router.get("/agents/", response_model=ResponseModel)
async def get_agents(db: Session = Depends(get_db)):
    agents = db.query(Agent).all()
    # Agent 无 project_id，通过其关联服务的部署方式统计，供前端区分「容器/Docker Compose 部署」与「二进制部署」
    deploy_rows = db.query(
        AppService.agent_uuid, AppService.deploy_type, func.count(AppService.id)
    ).filter(AppService.agent_uuid.isnot(None)).group_by(
        AppService.agent_uuid, AppService.deploy_type
    ).all()
    deploy_map = {}
    for agent_uuid, deploy_type, cnt in deploy_rows:
        deploy_map.setdefault(agent_uuid, {})[deploy_type] = int(cnt)

    result = []
    for agent in agents:
        deploy_types = deploy_map.get(agent.uuid, {})
        result.append({
            "id": agent.id,
            "uuid": agent.uuid,
            "hostname": agent.hostname,
            "ip": agent.ip,
            "os": agent.os,
            "os_distro": agent.os_distro,
            "kernel": agent.kernel,
            "arch": agent.arch,
            "cpu_model": agent.cpu_model,
            "cpu_cores": agent.cpu_cores,
            "memory_total": agent.memory_total,
            "agent_version": agent.agent_version,
            "capabilities": agent.capabilities,
            "tags": agent.tags,
            "status": agent.status,
            "is_online": manager.is_online(agent.uuid, agent.last_heartbeat),
            "last_heartbeat": agent.last_heartbeat,
            "service_count": sum(deploy_types.values()),
            "deploy_types": deploy_types,
            "deploy_type": agent.deploy_type,
            "deploy_dir": agent.deploy_dir,
            "compose_file": agent.compose_file,
            "binary_path": agent.binary_path,
            "service_name": agent.service_name,
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        })
    return ResponseModel(data=result, code=0)

@router.get("/agents/{agent_uuid}/", response_model=ResponseModel)
async def get_agent(agent_uuid: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.uuid == agent_uuid).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ResponseModel(data={
        "id": agent.id,
        "uuid": agent.uuid,
        "hostname": agent.hostname,
        "ip": agent.ip,
        "os": agent.os,
        "os_distro": agent.os_distro,
        "kernel": agent.kernel,
        "arch": agent.arch,
        "cpu_model": agent.cpu_model,
        "cpu_cores": agent.cpu_cores,
        "memory_total": agent.memory_total,
        "agent_version": agent.agent_version,
        "capabilities": agent.capabilities,
        "tags": agent.tags,
        "status": agent.status,
        "is_online": manager.is_online(agent_uuid, agent.last_heartbeat),
        "last_heartbeat": agent.last_heartbeat,
        "deploy_type": agent.deploy_type,
        "deploy_dir": agent.deploy_dir,
        "compose_file": agent.compose_file,
        "binary_path": agent.binary_path,
        "service_name": agent.service_name,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }, code=0)

@router.delete("/agents/{agent_uuid}/", response_model=ResponseModel)
async def delete_agent(agent_uuid: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.uuid == agent_uuid).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # 如果 Agent 在线，先断开连接
    if manager.is_online(agent_uuid):
        manager.disconnect(agent_uuid)
    
    # 清除该 Agent 关联服务的 agent_uuid
    services = db.query(AppService).filter(AppService.agent_uuid == agent_uuid).all()
    for service in services:
        service.agent_uuid = None
        # 清除缓存
        redis_client.delete(f"service_status:{service.id}")
        redis_client.delete(f"service_status_source:{service.id}")
    
    # 删除 Agent
    db.delete(agent)
    db.commit()
    
    # 清除缓存
    redis_client.delete(f"agent_metrics:{agent_uuid}")
    redis_client.delete(f"agent_containers:{agent_uuid}")
    redis_client.delete(f"agent_compose:{agent_uuid}")
    
    return ResponseModel(message="Agent deleted successfully", code=0)

@router.get("/agents/{agent_uuid}/services/", response_model=ResponseModel)
async def get_agent_services(agent_uuid: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.uuid == agent_uuid).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    services = db.query(AppService).filter(AppService.agent_uuid == agent_uuid).all()
    result = []
    for service in services:
        result.append({
            "id": service.id,
            "service_id": str(service.id),
            "name": service.func_desc,
            "username": service.username,
            "deploy_type": service.deploy_type,
            "pid_file": service.pid_file,
            "port": service.port,
            "health_url": service.health_url,
            "start_cmd": service.start_script,
            "stop_cmd": service.stop_script,
            "log_path": service.log_path,
            "docker_name": service.container_name,
            "compose_path": service.program_path,
        })
    return ResponseModel(data=result, code=0)

@router.get("/agents/{agent_uuid}/metrics/", response_model=ResponseModel)
async def get_agent_metrics(agent_uuid: str):
    try:
        metrics_str = redis_client.get(f"agent_metrics:{agent_uuid}")
        containers_str = redis_client.get(f"agent_containers:{agent_uuid}")
        compose_str = redis_client.get(f"agent_compose:{agent_uuid}")
        
        result = {}
        
        if metrics_str:
            result['system'] = json.loads(metrics_str.decode('utf-8'))
        else:
            result['system'] = {}
        
        if containers_str:
            result['docker_containers'] = json.loads(containers_str.decode('utf-8'))
        else:
            result['docker_containers'] = []
        
        if compose_str:
            result['compose_projects'] = json.loads(compose_str.decode('utf-8'))
        else:
            result['compose_projects'] = []
        
        return ResponseModel(data=result, code=0)
    except Exception as e:
        print(f"Get agent metrics error: {e}")
        return ResponseModel(data={"system": {}, "docker_containers": [], "compose_projects": []}, code=0)

@router.websocket("/ws/agent/{agent_uuid}")
async def agent_websocket(websocket: WebSocket, agent_uuid: str):
    print(f"[DEBUG] WebSocket connection attempt for agent: {agent_uuid}")
    print(f"[DEBUG] WebSocket path: {websocket.url.path}")
    print(f"[DEBUG] WebSocket query params: {websocket.query_params}")
    
    print(f"[DEBUG] Accepting WebSocket connection without validation")
    await manager.connect(websocket, agent_uuid)
    
    db = next(get_db())
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await handle_agent_message(message, agent_uuid, db)
            except json.JSONDecodeError as e:
                print(f"Invalid JSON: {e}")
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
    except WebSocketDisconnect:
        # 仅当这条连接仍是当前注册连接时才清理；旧连接延迟断开（Agent 已重连）时跳过，
        # 否则会把在线的新连接误判为离线
        if not manager.disconnect(agent_uuid, websocket):
            return
        agent = db.query(Agent).filter(Agent.uuid == agent_uuid).first()
        if agent:
            agent.status = 'offline'
            db.commit()
            
            # Agent 断连后，关联服务不再回退 SSH 检测
            # 直接将状态置为 UNKNOWN 并标记来源为 OFFLINE，让前端明确感知"Agent 离线"
            try:
                services = db.query(AppService).filter(AppService.agent_uuid == agent_uuid).all()
                for service in services:
                    redis_client.set(f"service_status:{service.id}", "UNKNOWN", ex=30)
                    redis_client.set(f"service_status_source:{service.id}", "OFFLINE", ex=30)
                print(f"Cleared cache for {len(services)} services of disconnected agent {agent_uuid} (OFFLINE)")
            except Exception as e:
                print(f"Clear cache error: {e}")
                
        print(f"Agent {agent_uuid} disconnected")
    except Exception as e:
        # 消息处理中的非预期异常不应让协程静默退出而留下死连接
        print(f"Agent {agent_uuid} websocket loop error: {e}")
        import traceback
        traceback.print_exc()
        manager.disconnect(agent_uuid, websocket)
    finally:
        db.close()

async def handle_agent_message(message: dict, agent_uuid: str, db: Session):
    msg_type = message.get('type', '')
    
    if msg_type == 'register':
        await handle_register(message, agent_uuid, db)
    elif msg_type == 'heartbeat':
        await handle_heartbeat(message, agent_uuid, db)
    elif msg_type == 'services':
        await handle_services(message, agent_uuid, db)
    elif msg_type == 'command_result':
        await handle_command_result(message, agent_uuid, db)
    elif msg_type == 'pull_services':
        await handle_pull_services(message, agent_uuid, db)
    elif msg_type == 'log_line':
        await handle_log_line(message, agent_uuid, db)
    elif msg_type == 'update_progress':
        await handle_update_progress(message, agent_uuid, db)

async def handle_update_progress(message: dict, agent_uuid: str, db: Session):
    """处理 Agent 上报的批量更新进度，更新明细与任务统计。"""
    data = message.get('data', {})
    task_id = data.get('task_id', '')
    print(f"[UPDATE_PROGRESS] recv agent={agent_uuid} task={task_id} "
          f"step={data.get('step')} status={data.get('status')} progress={data.get('progress')}")
    if not task_id:
        return

    # 使用独立会话，避免与 WebSocket 长连接会话、执行器会话之间状态相互干扰
    from core.database import SessionLocal
    import services.agent_update_service as aus
    s = SessionLocal()
    try:
        aus.update_item_progress(
            s, task_id, agent_uuid,
            step=data.get('step'),
            status=data.get('status'),
            progress=data.get('progress'),
            error=data.get('error'),
        )
    finally:
        s.close()
    print(f"Update progress from {agent_uuid} task={task_id} step={data.get('step')} status={data.get('status')}")


async def handle_log_line(message: dict, agent_uuid: str, db: Session):
    data = message.get('data', {})
    service_id = data.get('service_id', '')
    
    if service_id:
        log_message = {
            "type": "log_line",
            "service_id": service_id,
            "line": data.get('line', ''),
            "timestamp": data.get('timestamp', datetime.now().timestamp())
        }
        
        await manager.broadcast_log(service_id, log_message)
        
        print(f"Log line from {agent_uuid} for service {service_id}: {data.get('line', '')[:50]}...")

async def handle_register(message: dict, agent_uuid: str, db: Session):
    data = message.get('data', {})
    registration = data.get('registration', {})
    
    agent = db.query(Agent).filter(Agent.uuid == agent_uuid).first()
    
    if not agent:
        ip = registration.get('ip', '')
        if ip:
            # 查找同一 IP 的任意 Agent 记录
            existing_agent = db.query(Agent).filter(Agent.ip == ip).order_by(Agent.last_heartbeat.desc()).first()
            if existing_agent:
                # 复用旧 Agent 记录（无论在线或离线）
                old_uuid = existing_agent.uuid
                if old_uuid != agent_uuid:
                    existing_agent.uuid = agent_uuid
                    # 更新关联的服务
                    services = db.query(AppService).filter(AppService.agent_uuid == old_uuid).all()
                    for service in services:
                        service.agent_uuid = agent_uuid
                    if services:
                        db.commit()
                        print(f"Updated {len(services)} services from {old_uuid} to {agent_uuid}")
                    print(f"Reused agent {old_uuid} -> {agent_uuid} for IP {ip} (was {existing_agent.status})")
                # 无论 UUID 是否变化，都要把 agent 指向复用的记录，
                # 否则后续 agent.hostname 赋值会因 agent 为 None 抛异常导致注册失败
                agent = existing_agent
            else:
                # 新 IP，创建新 Agent
                agent = Agent(uuid=agent_uuid)
                print(f"New agent created: {agent_uuid} for IP {ip}")
        else:
            agent = Agent(uuid=agent_uuid)
    
    agent.hostname = registration.get('hostname', '')
    agent.ip = registration.get('ip', '')
    agent.os = registration.get('os', '')
    agent.os_distro = registration.get('os_distro', '') or None
    agent.kernel = registration.get('kernel', '')
    agent.arch = registration.get('arch', '')
    agent.cpu_model = registration.get('cpu_model', '')
    agent.cpu_cores = registration.get('cpu_cores', 0)
    agent.memory_total = registration.get('memory_total', 0)
    agent.agent_version = registration.get('agent_version', '')
    agent.capabilities = registration.get('capabilities', [])
    agent.tags = registration.get('tags', [])
    agent.status = 'online'
    agent.last_heartbeat = datetime.now()

    # 部署元信息（Agent 上报，批量更新下发时使用）
    # 新旧字段兼容：deploy_method（新）优先，deploy_type（旧）兜底
    deploy_method = registration.get('deploy_method', '')
    deploy_type = deploy_method or registration.get('deploy_type', '')
    if deploy_type:
        agent.deploy_type = deploy_type
    deploy_dir = registration.get('deploy_dir', '')
    if deploy_dir:
        agent.deploy_dir = deploy_dir
    compose_file = registration.get('compose_file', '')
    if compose_file:
        agent.compose_file = compose_file
    binary_path = registration.get('binary_path', '')
    if binary_path:
        agent.binary_path = binary_path
    svc_name = registration.get('service_name', '')
    if svc_name:
        agent.service_name = svc_name
    
    db.add(agent)
    db.commit()
    
    print(f"Agent registered: {agent_uuid} - {agent.hostname} ({agent.ip})")
    
    if agent.ip:
        # 自动关联：把该 IP 上尚未关联 Agent 的服务挂到本 Agent 名下。
        # 注意这里只处理"未关联"的服务，已关联到其他 Agent 的服务不动
        # （服务可能部署在 Agent 管理的其他机器上，不能按 IP 强行改绑）。
        services_to_associate = db.query(AppService).filter(
            AppService.ip == agent.ip,
            (AppService.agent_uuid == "") | (AppService.agent_uuid == None)
        ).all()
        
        if services_to_associate:
            print(f"Auto-associating {len(services_to_associate)} services to agent {agent_uuid}")
            for service in services_to_associate:
                service.agent_uuid = agent_uuid
                # 清除旧缓存，等待 Agent 重新上报
                redis_client.delete(f"service_status:{service.id}")
                redis_client.delete(f"service_status_source:{service.id}")
                print(f"  - Service {service.id}: {service.func_desc} (cleared cache)")
            db.commit()
    
    pull_message = {
        "type": "pull_services",
        "request_id": "",
        "timestamp": datetime.now().timestamp(),
        "data": {}
    }
    await manager.send_message(agent_uuid, pull_message)

def _load_run_mode_map(db: Session, services: list) -> dict:
    """批量加载本次心跳涉及服务的容器运行类型配置。

    返回 {service_id(str): {container_name: run_mode}}。
    无配置的容器不在 map 中，由领域层按默认值 permanent 处理。
    """
    result = {}
    try:
        service_ids = []
        for s in services:
            sid = s.get('service_id')
            if sid:
                try:
                    service_ids.append(int(sid))
                except (TypeError, ValueError):
                    continue
        if not service_ids:
            return result
        rows = (
            db.query(ServiceContainerConfig)
            .filter(ServiceContainerConfig.service_id.in_(service_ids))
            .all()
        )
        for r in rows:
            result.setdefault(str(r.service_id), {})[r.container_name] = r.run_mode
    except Exception as e:
        print(f"Load run_mode map error: {e}")
    return result


async def handle_heartbeat(message: dict, agent_uuid: str, db: Session):
    # 心跳处理包含同步 DB 查询与 Redis 写入，21 台 Agent 每 15s 一次，
    # 若直接在事件循环里执行会周期性阻塞所有 HTTP 请求（表现为页面偶发卡顿）。
    # 因此整体丢到线程池执行，事件循环只负责 await。
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _handle_heartbeat_sync, message, agent_uuid, db)


def _handle_heartbeat_sync(message: dict, agent_uuid: str, db: Session):
    data = message.get('data', {})
    heartbeat = data.get('heartbeat', {})
    system = heartbeat.get('system', {})
    
    agent = db.query(Agent).filter(Agent.uuid == agent_uuid).first()
    if agent:
        agent.status = 'online'
        agent.last_heartbeat = datetime.now()
        # 操作系统发行版只在信息变化时更新，避免每次心跳重复写入相同值
        os_distro = (system or {}).get('os_distro') or ''
        if os_distro and os_distro != (agent.os_distro or ''):
            agent.os_distro = os_distro
        db.commit()
    
    services = heartbeat.get('services', [])
    docker_containers = heartbeat.get('docker_containers', [])
    compose_projects = heartbeat.get('compose_projects', [])
    # 告警中心：收集本次心跳各服务的业务状态，循环结束后统一批量评估
    alert_items = []

    try:
        # 一次性任务/常驻服务的运行类型配置（容器级），用于业务状态计算
        run_mode_map = _load_run_mode_map(db, services)

        for service_status in services:
            service_id = service_status.get('service_id')
            if service_id:
                status = service_status.get('status', 'UNKNOWN')
                name = service_status.get('name', '')
                pid = service_status.get('pid', 0)
                containers = service_status.get('containers', [])
                redis_key = f"service_status:{service_id}"
                source_key = f"service_status_source:{service_id}"

                # 有容器明细时，由后端领域层按 run_mode + Docker 实际状态重算业务状态，
                # 覆盖 Agent 端基于"存在 Exited 即 Partial"的粗判，
                # 避免一次性任务正常退出（exited+0）被误判为部分运行/异常。
                if containers:
                    biz_status = container_status_service.compute_service_status(
                        containers, run_mode_map.get(str(service_id), {})
                    )
                    status = biz_status
                else:
                    # 无容器服务（物理机 HOST/PROCESS）：按服务级默认运行类型计算，
                    # inactive 时未运行属预期状态，不告警。
                    svc_mode_map = run_mode_map.get(str(service_id), {})
                    svc_mode = container_status_service.resolve_run_mode(svc_mode_map, None)
                    status = container_status_service.compute_host_service_status(status, svc_mode)

                # 告警中心：收集本服务最终业务状态（不读取 old_status，DB 为唯一真相源）
                alert_items.append((service_id, status))

                # 【新增】先读取旧状态用于变化检测
                old_status_bytes = redis_client.get(redis_key)
                old_status = old_status_bytes.decode('utf-8') if old_status_bytes else None

                # 【新增】计算当前时间戳
                current_timestamp = int(time.time())

                # 【修改】每次心跳更新"状态最后更新时间"（移到状态变化判断之前）
                redis_client.set(f"status_last_seen_at:{service_id}", current_timestamp)

                # 【修改】状态变化检测和停止时间记录（仅检测停止状态）
                # 状态常量统一为大写（RUNNING/STOPPED/PARTIAL），此处必须大写比较，
                # 否则条件恒为 False，stopped_at 永远不会写入。
                should_update_stopped_at = (
                    status == "STOPPED" and old_status in ["RUNNING", "PARTIAL"]
                )

                # 【修改】记录停止时间（如果需要）
                if should_update_stopped_at:
                    redis_client.set(f"stopped_at:{service_id}", current_timestamp)

                # 缓存 TTL 60s，是心跳间隔 15s 的 4 倍，容忍心跳延迟
                redis_client.set(redis_key, status, ex=60)
                redis_client.set(source_key, "AGENT", ex=60)
                # 存储容器详情，用于 Docker Compose 服务的容器列表展示
                if containers:
                    redis_client.set(
                        f"service_containers:{service_id}",
                        json.dumps(containers),
                        ex=60
                    )
                    print(f"  Service {service_id} ({name}): status={status}, pid={pid}, containers={len(containers)}, redis_key={redis_key}, source_key={source_key}")
                else:
                    redis_client.delete(f"service_containers:{service_id}")
                    print(f"  Service {service_id} ({name}): status={status}, pid={pid}, redis_key={redis_key}, source_key={source_key}")
        
        system_json = json.dumps(system)
        redis_client.set(f"agent_metrics:{agent_uuid}", system_json, ex=60)
        
        if docker_containers:
            containers_json = json.dumps(docker_containers)
            redis_client.set(f"agent_containers:{agent_uuid}", containers_json, ex=60)
        
        if compose_projects:
            compose_json = json.dumps(compose_projects)
            redis_client.set(f"agent_compose:{agent_uuid}", compose_json, ex=60)
    except Exception as e:
        print(f"Redis cache error: {e}")

    # 告警中心：批量评估（去重/状态机/恢复），数据库为唯一真相源
    try:
        summary = alert_service.evaluate_heartbeat_statuses(db, alert_items, agent_uuid)
        if summary.get('created') or summary.get('recovered'):
            print(f"[Alert] agent={agent_uuid} created={summary.get('created')} updated={summary.get('updated')} recovered={summary.get('recovered')}")
    except Exception as e:
        print(f"[Alert] evaluate failed: {e}")

    print(f"Heartbeat from {agent_uuid}: CPU={system.get('cpu_percent', 0)}%, Memory={system.get('memory_percent', 0)}%, Services={len(services)}")

async def handle_services(message: dict, agent_uuid: str, db: Session):
    data = message.get('data', {})
    print(f"Services from {agent_uuid}: {data}")

async def handle_command_result(message: dict, agent_uuid: str, db: Session):
    data = message.get('data', {})
    request_id = message.get('request_id', '')
    
    manager.resolve_pending_request(request_id, data)
    
    print(f"Command result from {agent_uuid}, request_id={request_id}: {data}")

async def handle_pull_services(message: dict, agent_uuid: str, db: Session):
    agent = db.query(Agent).filter(Agent.uuid == agent_uuid).first()
    if not agent:
        print(f"Agent not found: {agent_uuid}")
        return
    
    # 按 agent_uuid 关联取服务，与注册自动关联、Agent 详情等处的口径保持一致。
    # 不能用 AppService.ip == agent.ip：agent.ip 是 Agent 自身所在机器的 IP，
    # 而服务可能部署在 Agent 管理的其他机器上（服务 IP 与 Agent IP 不同），
    # 用 IP 过滤会漏掉这些服务，导致 Agent 内存里始终是旧的服务列表
    # （改了 program_path 等配置后不生效，日志里还在报旧路径找不到 compose 文件）。
    services = db.query(AppService).filter(AppService.agent_uuid == agent_uuid).all()
    
    service_list = []
    for service in services:
        port = service.port or 0
        ports_str = str(port) if port else ""
        
        start_cmd = service.start_script
        if start_cmd and service.program_path and not start_cmd.startswith(('/', '~')):
            start_cmd = f"{service.program_path.rstrip('/')}/{start_cmd}"
        
        stop_cmd = service.stop_script
        if stop_cmd and service.program_path and not stop_cmd.startswith(('/', '~')):
            stop_cmd = f"{service.program_path.rstrip('/')}/{stop_cmd}"
        
        service_list.append({
            "service_id": str(service.id),
            "name": service.func_desc,
            "username": service.username,
            "deploy_type": service.deploy_type,
            "pid_file": service.pid_file,
            "port": port,
            "ports": ports_str,
            "health_url": service.health_url,
            "start_cmd": start_cmd,
            "stop_cmd": stop_cmd,
            "restart_cmd": "",
            "log_path": service.log_path,
            "docker_name": service.container_name,
            "image_name": service.image_name,
            "compose_path": service.program_path,
            "program_path": service.program_path,
        })
    
    response = {
        "type": "services",
        "request_id": message.get('request_id', ''),
        "timestamp": datetime.now().timestamp(),
        "data": {
            "services": service_list,
            "version": 1,
        }
    }
    
    await manager.send_message(agent_uuid, response)
    print(f"Sent {len(service_list)} services to agent {agent_uuid} (IP: {agent.ip})")

@router.get("/debug/service-status/{service_id}")
async def debug_service_status(service_id: int, user = Depends(get_current_user)):
    status = redis_client.get(f"service_status:{service_id}")
    source = redis_client.get(f"service_status_source:{service_id}")
    
    return {
        "service_id": service_id,
        "status": status.decode('utf-8') if status else None,
        "source": source.decode('utf-8') if source else None,
    }

@router.get("/debug/all-status")
async def debug_all_status(user = Depends(get_current_user)):
    keys = redis_client.keys("service_status:*")
    result = {}
    for key in keys:
        key_str = key.decode('utf-8')
        sid = key_str.split(":")[-1]
        status = redis_client.get(key)
        source_key = f"service_status_source:{sid}"
        source = redis_client.get(source_key)
        result[sid] = {
            "status": status.decode('utf-8') if status else None,
            "source": source.decode('utf-8') if source else None,
        }
    return result

# ==================== Agent 控制 API ====================

async def control_agent_process(agent: Agent, action: str, db: Session = None, user=None) -> dict:
    """
    通过 SSH 控制 Agent 进程（start/stop/restart/status）

    按 agent.deploy_type 分流：
    - binary：systemctl / SysV init 管理 srmc-agent 服务
    - docker：docker compose 管理 srmc-agent 容器

    凭据优先级：agents 表自带的 ssh 凭据 → servers 表按 IP 匹配。
    """
    service_name = agent.service_name or "srmc-agent"
    deploy_type = (agent.deploy_type or "binary").strip().lower()

    # 解析 SSH 凭据（agents 优先，缺失时回退 servers 表）
    if db is not None:
        port, username, password = resolve_agent_ssh_credentials(db, agent, user)
    else:
        from utils.crypto import decrypt
        port = agent.ssh_port or 22
        username = agent.ssh_username
        try:
            password = decrypt(agent.ssh_password) if agent.ssh_password else None
        except Exception:
            password = None

    if not username or not password:
        return {"success": False, "message": f"Agent {agent.hostname} 未配置 SSH 凭据（Agent 管理与服务器管理均无该 IP 记录）"}

    if deploy_type == "docker":
        cmd = _build_docker_control_cmd(agent, action, service_name)
    else:
        cmd = _build_binary_control_cmd(action, service_name)

    if not cmd:
        return {"success": False, "message": f"未知操作: {action}"}

    try:
        conn = await ssh_pool.get_connection(agent.ip, port, username, password)

        if not conn:
            return {"success": False, "message": f"无法连接到 Agent {agent.hostname} ({agent.ip})"}

        output, error, success = await conn.execute_command(cmd)

        if not success:
            return {"success": False, "message": f"SSH 执行失败: {error}"}

        # 分析输出
        output = output.strip()
        if action == "status":
            is_running = _parse_agent_running(deploy_type, output)
            return {"success": True, "message": f"Agent {agent.hostname} 状态: {'运行中' if is_running else '已停止'}", "output": output}
        else:
            return {"success": True, "message": f"Agent {agent.hostname} {action} 成功", "output": output}

    except Exception as e:
        return {"success": False, "message": f"控制 Agent 失败: {str(e)}"}


def _build_binary_control_cmd(action: str, service_name: str) -> str:
    """二进制部署：优先 systemctl，无 systemd 时回退 SysV init（CentOS 6）。"""
    if action == "status":
        # 同时兼容 systemd 与 SysV：先试 systemctl，失败则用 service 查询
        return (
            f"if command -v systemctl >/dev/null 2>&1; then "
            f"systemctl is-active {service_name}; "
            f"else service {service_name} status >/dev/null 2>&1 && echo active || echo inactive; fi"
        )
    if action in ("start", "stop", "restart"):
        return (
            f"if command -v systemctl >/dev/null 2>&1; then "
            f"sudo systemctl {action} {service_name}; "
            f"else sudo service {service_name} {action}; fi"
        )
    return ""


def _build_docker_control_cmd(agent: Agent, action: str, service_name: str) -> str:
    """Docker 部署：用 docker compose 管理 Agent 容器。

    compose 文件路径优先取 agent.compose_file，缺省用 /etc/srmc-agent/docker-compose.yml。
    兼容 docker compose（v2 插件）与 docker-compose（v1 独立命令）。
    """
    compose_file = (agent.compose_file or "/etc/srmc-agent/docker-compose.yml").strip()
    # 统一用 docker compose 前缀，由 shell 自动选择可用命令
    dc = (
        f"if docker compose version >/dev/null 2>&1; then DC='docker compose'; "
        f"else DC='docker-compose'; fi; "
    )
    base = f"{dc}cd $(dirname {compose_file}) && $DC -f {compose_file}"

    if action == "start":
        return f"{base} up -d"
    if action == "stop":
        return f"{base} stop"
    if action == "restart":
        return f"{base} restart"
    if action == "status":
        # 用容器名精确查询，避免 compose 项目名差异
        return (
            f"docker ps --filter name=^{service_name}$ --filter status=running "
            f"--format '{{{{.Names}}}}' | grep -q . && echo active || echo inactive"
        )
    return ""


def _parse_agent_running(deploy_type: str, output: str) -> bool:
    """解析 status 命令输出，判断 Agent 是否运行中。"""
    out = (output or "").strip().lower()
    if deploy_type == "docker":
        # docker 分支输出 active/inactive
        return out == "active"
    # 二进制分支：systemd 输出 active，SysV 回退输出 active
    return out == "active"

@router.post("/agents/{agent_uuid}/control")
async def control_agent(
    agent_uuid: str, 
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    控制单个 Agent 进程（start/stop/restart/status）
    """
    agent = db.query(Agent).filter(Agent.uuid == agent_uuid).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    action = payload.get("action", "")
    if action not in ("start", "stop", "restart", "status"):
        raise HTTPException(status_code=400, detail="无效的操作，支持: start, stop, restart, status")
    
    result = await control_agent_process(agent, action, db, user)
    
    # 记录审计日志
    if action != "status":
        from services.audit_service import log_audit
        log_audit(db, user.id, user.username, "AGENT_CONTROL",
                  result="success" if result.get("success") else "failed",
                  output=f"Agent: {agent.hostname}, 操作: {action}, 结果: {result.get('message')}")
    
    return ResponseModel(data=result)

@router.post("/agents/batch-control")
async def batch_control_agents(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    批量控制 Agent 进程
    """
    agent_uuids = payload.get("agent_uuids", [])
    action = payload.get("action", "")
    
    if not agent_uuids:
        raise HTTPException(status_code=400, detail="未选择任何 Agent")
    
    if action not in ("start", "stop", "restart", "status"):
        raise HTTPException(status_code=400, detail="无效的操作，支持: start, stop, restart, status")
    
    # 查询所有 Agent
    agents = db.query(Agent).filter(Agent.uuid.in_(agent_uuids)).all()
    
    results = []
    success_count = 0
    fail_count = 0
    
    # 并发执行（使用 gather）
    tasks = [control_agent_process(agent, action, db, user) for agent in agents]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for agent, result in zip(agents, task_results):
        if isinstance(result, Exception):
            results.append({
                "agent_uuid": agent.uuid,
                "hostname": agent.hostname,
                "ip": agent.ip,
                "success": False,
                "message": f"异常: {str(result)}"
            })
            fail_count += 1
        else:
            results.append({
                "agent_uuid": agent.uuid,
                "hostname": agent.hostname,
                "ip": agent.ip,
                "success": result.get("success", False),
                "message": result.get("message", "")
            })
            if result.get("success"):
                success_count += 1
            else:
                fail_count += 1
    
    # 记录审计日志
    if action != "status":
        from services.audit_service import log_audit
        log_audit(db, user.id, user.username, "AGENT_BATCH_CONTROL",
                  result="success" if fail_count == 0 else "partial",
                  output=f"批量操作: {action}, 总数: {len(agents)}, 成功: {success_count}, 失败: {fail_count}")
    
    return ResponseModel(data={
        "action": action,
        "total": len(agents),
        "success": success_count,
        "failed": fail_count,
        "results": results
    })

@router.post("/agents/batch-delete")
async def batch_delete_agents(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user = Depends(require_permission("agent_manage"))
):
    """批量删除 Agent。

    逐台执行与单删一致的处理：断开连接、解除关联服务绑定并清理缓存。
    每台独立提交，单台失败不影响其他主机。
    """
    agent_uuids = payload.get("agent_uuids", [])
    if not agent_uuids:
        raise HTTPException(status_code=400, detail="未选择任何 Agent")

    agents = db.query(Agent).filter(Agent.uuid.in_(agent_uuids)).all()

    results = []
    success_count = 0
    fail_count = 0

    for agent in agents:
        agent_uuid = agent.uuid
        hostname = agent.hostname
        ip = agent.ip
        try:
            # 如果 Agent 在线，先断开连接
            if manager.is_online(agent_uuid):
                manager.disconnect(agent_uuid)

            # 解除该 Agent 关联服务的绑定
            services = db.query(AppService).filter(AppService.agent_uuid == agent_uuid).all()
            for service in services:
                service.agent_uuid = None

            db.delete(agent)
            db.commit()

            # 清除缓存
            for service in services:
                redis_client.delete(f"service_status:{service.id}")
                redis_client.delete(f"service_status_source:{service.id}")
            redis_client.delete(f"agent_metrics:{agent_uuid}")
            redis_client.delete(f"agent_containers:{agent_uuid}")
            redis_client.delete(f"agent_compose:{agent_uuid}")

            success_count += 1
            results.append({
                "agent_uuid": agent_uuid,
                "hostname": hostname,
                "ip": ip,
                "success": True,
                "message": "删除成功",
            })
        except Exception as e:
            db.rollback()
            fail_count += 1
            results.append({
                "agent_uuid": agent_uuid,
                "hostname": hostname,
                "ip": ip,
                "success": False,
                "message": f"删除失败: {e}",
            })

    return ResponseModel(data={
        "total": len(agents),
        "success": success_count,
        "failed": fail_count,
        "results": results,
    })

# 机器架构别名归一：uname -m 输出 → Go 侧架构命名（amd64/arm64），与更新包命名对齐
_ARCH_ALIASES = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
    "i386": "386",
    "i486": "386",
    "i586": "386",
    "i686": "386",
    "armv6l": "arm",
    "armv7l": "arm",
    "ppc64": "ppc64",
    "ppc64le": "ppc64le",
    "s390x": "s390x",
    "riscv64": "riscv64",
    "loongarch64": "loong64",
}


def _normalize_arch(raw: str) -> str:
    return _ARCH_ALIASES.get((raw or "").strip().lower(), "")


def resolve_agent_ssh_credentials(db: Session, agent: Agent, user=None):
    """解析 Agent 所在机器的 SSH 凭据，返回 (port, username, password)。

    凭据优先级：agents 表自带的 ssh 凭据 → servers 表按 IP 匹配。
    servers 回退时按组织隔离（非超管只能看到本组织的服务器记录）。

    两处凭据是独立存储的（agents.ssh_* 与 servers.username/password），
    这里统一回退逻辑，避免各功能各写一套导致行为不一致。
    """
    from utils.crypto import decrypt
    from models.server import Server

    port = agent.ssh_port or 22
    username = agent.ssh_username
    try:
        password = decrypt(agent.ssh_password) if agent.ssh_password else None
    except Exception:
        password = None

    if not username or not password:
        sq = db.query(Server).filter(Server.ip == agent.ip)
        if user is not None:
            from services.data_scope_service import DataScopeService
            if not DataScopeService._is_super_admin(user) and user.organization_id is not None:
                sq = sq.filter(Server.organization_id == user.organization_id)
        srv = sq.first()
        if srv:
            port = srv.ssh_port or 22
            username = srv.username
            try:
                password = decrypt(srv.password) if srv.password else None
            except Exception:
                password = None

    return port, username, password


async def _probe_agent_arch(db: Session, user, agent: Agent):
    """SSH 探测目标机架构，返回 (arch, err)。

    凭据优先级：agents 表自带的 ssh 凭据 → servers 表按 IP 匹配（按组织隔离）。
    """
    port, username, password = resolve_agent_ssh_credentials(db, agent, user)

    if not username or not password:
        return "", "缺少可用的 SSH 凭据（Agent 未配置，servers 表也无该 IP 记录）"

    try:
        conn = await ssh_pool.get_connection(agent.ip, port, username, password)
        if not conn:
            return "", f"无法 SSH 连接 {agent.ip}:{port}"
        output, error, success = await conn.execute_command("uname -m")
        if not success:
            return "", f"执行 uname -m 失败: {error}"
        arch = _normalize_arch(output)
        if not arch:
            return "", f"无法识别的架构输出: {output.strip()[:50]}"
        return arch, ""
    except Exception as e:
        return "", f"探测失败: {e}"


@router.post("/agents/probe-arch")
async def probe_agents_arch(
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
    user=Depends(require_permission("agent_manage")),
):
    """SSH 探测并回写 Agent 所在机器的架构。

    不传 agent_uuids 时，自动探测所有 arch 为空的 Agent（存量数据补录）。
    """
    agent_uuids = (payload or {}).get("agent_uuids") or []
    query = db.query(Agent)
    if agent_uuids:
        query = query.filter(Agent.uuid.in_(agent_uuids))
    else:
        query = query.filter((Agent.arch.is_(None)) | (Agent.arch == ""))
    agents = query.all()

    if not agents:
        return ResponseModel(data={"total": 0, "success": 0, "failed": 0, "results": []})

    probed = await asyncio.gather(
        *[_probe_agent_arch(db, user, a) for a in agents], return_exceptions=True
    )

    results = []
    success_count = 0
    for agent, result in zip(agents, probed):
        if isinstance(result, Exception):
            arch, err = "", f"异常: {result}"
        else:
            arch, err = result
        if arch:
            agent.arch = arch
            success_count += 1
        results.append({
            "agent_uuid": agent.uuid,
            "hostname": agent.hostname,
            "ip": agent.ip,
            "arch": arch,
            "success": bool(arch),
            "message": err,
        })
    db.commit()

    from services.audit_service import log_audit
    log_audit(db, user.id, user.username, "AGENT_CONTROL",
              result="success" if success_count == len(agents) else "partial",
              output=f"探测 Agent 架构 总数={len(agents)} 成功={success_count}")

    return ResponseModel(data={
        "total": len(agents),
        "success": success_count,
        "failed": len(agents) - success_count,
        "results": results,
    })


@router.put("/agents/{agent_uuid}/config")
async def update_agent_config(
    agent_uuid: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    更新 Agent 控制配置（SSH 凭据、服务名等）
    """
    from utils.crypto import encrypt
    agent = db.query(Agent).filter(Agent.uuid == agent_uuid).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # 更新可配置字段
    if "ssh_port" in payload:
        agent.ssh_port = payload["ssh_port"]
    if "ssh_username" in payload:
        agent.ssh_username = payload["ssh_username"]
    if "ssh_password" in payload and payload["ssh_password"]:
        # 加密存储密码
        agent.ssh_password = encrypt(payload["ssh_password"])
    if "service_name" in payload:
        agent.service_name = payload["service_name"]
    
    db.commit()
    
    return ResponseModel(data={
        "agent_uuid": agent.uuid,
        "hostname": agent.hostname,
        "ssh_configured": bool(agent.ssh_username and agent.ssh_password),
        "service_name": agent.service_name
    }, message="Agent 配置更新成功")