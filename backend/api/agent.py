from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, Query, Header, Body
from fastapi.websockets import WebSocketState
from sqlalchemy.orm import Session
from starlette.websockets import WebSocket as StarletteWebSocket
from core.database import get_db
from models.agent import Agent
from models.app_service import AppService
from schemas.common import ResponseModel
from utils.redis_client import redis_client
from utils.ssh_pool import ssh_pool
from core.config import settings
from api.dependencies import get_current_user
import json
import asyncio
from datetime import datetime
import uuid

router = APIRouter()

class AgentConnectionManager:
    def __init__(self):
        self.active_connections = {}
        self.pending_requests = {}
        self.log_subscribers = {}
    
    async def connect(self, websocket: WebSocket, agent_uuid: str):
        await websocket.accept()
        self.active_connections[agent_uuid] = websocket
    
    def disconnect(self, agent_uuid: str):
        if agent_uuid in self.active_connections:
            del self.active_connections[agent_uuid]
    
    async def send_message(self, agent_uuid: str, message: dict):
        if agent_uuid in self.active_connections:
            try:
                await self.active_connections[agent_uuid].send_json(message)
                return True
            except Exception as e:
                print(f"Send message failed: {e}")
                return False
        return False
    
    def is_online(self, agent_uuid: str) -> bool:
        return agent_uuid in self.active_connections
    
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
    result = []
    for agent in agents:
        result.append({
            "id": agent.id,
            "uuid": agent.uuid,
            "hostname": agent.hostname,
            "ip": agent.ip,
            "os": agent.os,
            "kernel": agent.kernel,
            "arch": agent.arch,
            "cpu_model": agent.cpu_model,
            "cpu_cores": agent.cpu_cores,
            "memory_total": agent.memory_total,
            "agent_version": agent.agent_version,
            "capabilities": agent.capabilities,
            "tags": agent.tags,
            "status": agent.status,
            "is_online": manager.is_online(agent.uuid),
            "last_heartbeat": agent.last_heartbeat,
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
        "kernel": agent.kernel,
        "arch": agent.arch,
        "cpu_model": agent.cpu_model,
        "cpu_cores": agent.cpu_cores,
        "memory_total": agent.memory_total,
        "agent_version": agent.agent_version,
        "capabilities": agent.capabilities,
        "tags": agent.tags,
        "status": agent.status,
        "is_online": manager.is_online(agent_uuid),
        "last_heartbeat": agent.last_heartbeat,
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
        manager.disconnect(agent_uuid)
        agent = db.query(Agent).filter(Agent.uuid == agent_uuid).first()
        if agent:
            agent.status = 'offline'
            db.commit()
            
            # 清除该 Agent 关联服务的缓存，强制使用 SSH
            try:
                services = db.query(AppService).filter(AppService.agent_uuid == agent_uuid).all()
                for service in services:
                    redis_client.set(f"service_status:{service.id}", "STOPPED", ex=30)
                    redis_client.set(f"service_status_source:{service.id}", "SSH", ex=30)
                print(f"Cleared cache for {len(services)} services of disconnected agent {agent_uuid}")
            except Exception as e:
                print(f"Clear cache error: {e}")
                
        print(f"Agent {agent_uuid} disconnected")
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
                else:
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
    
    db.add(agent)
    db.commit()
    
    print(f"Agent registered: {agent_uuid} - {agent.hostname} ({agent.ip})")
    
    if agent.ip:
        services_to_associate = db.query(AppService).filter(
            AppService.ip == agent.ip,
            (AppService.agent_uuid == "") | (AppService.agent_uuid == None) | (AppService.agent_uuid != agent_uuid)
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

async def handle_heartbeat(message: dict, agent_uuid: str, db: Session):
    data = message.get('data', {})
    heartbeat = data.get('heartbeat', {})
    
    agent = db.query(Agent).filter(Agent.uuid == agent_uuid).first()
    if agent:
        agent.status = 'online'
        agent.last_heartbeat = datetime.now()
        db.commit()
    
    system = heartbeat.get('system', {})
    services = heartbeat.get('services', [])
    docker_containers = heartbeat.get('docker_containers', [])
    compose_projects = heartbeat.get('compose_projects', [])
    
    try:
        for service_status in services:
            service_id = service_status.get('service_id')
            if service_id:
                status = service_status.get('status', 'UNKNOWN')
                name = service_status.get('name', '')
                pid = service_status.get('pid', 0)
                containers = service_status.get('containers', [])
                redis_key = f"service_status:{service_id}"
                source_key = f"service_status_source:{service_id}"
                redis_client.set(redis_key, status, ex=15)
                redis_client.set(source_key, "AGENT", ex=15)
                # 存储容器详情，用于 Docker Compose 服务的 Partial 状态展示
                if containers:
                    redis_client.set(
                        f"service_containers:{service_id}",
                        json.dumps(containers),
                        ex=15
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
    
    services = db.query(AppService).filter(AppService.ip == agent.ip).all()
    
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

async def control_agent_process(agent: Agent, action: str) -> dict:
    """
    通过 SSH 控制 Agent 进程（start/stop/restart）
    使用 systemctl 管理 Agent 服务
    """
    from utils.crypto import decrypt
    
    # 检查 Agent 是否配置了 SSH 凭据
    if not agent.ssh_username or not agent.ssh_password:
        return {"success": False, "message": f"Agent {agent.hostname} 未配置 SSH 凭据"}
    
    service_name = agent.service_name or "srmc-agent"
    port = agent.ssh_port or 22
    
    # 构建 systemctl 命令
    if action == "start":
        cmd = f"sudo systemctl start {service_name}"
    elif action == "stop":
        cmd = f"sudo systemctl stop {service_name}"
    elif action == "restart":
        cmd = f"sudo systemctl restart {service_name}"
    elif action == "status":
        cmd = f"systemctl is-active {service_name}"
    else:
        return {"success": False, "message": f"未知操作: {action}"}
    
    try:
        password = decrypt(agent.ssh_password) if agent.ssh_password else None
        conn = await ssh_pool.get_connection(agent.ip, port, agent.ssh_username, password)
        
        if not conn:
            return {"success": False, "message": f"无法连接到 Agent {agent.hostname} ({agent.ip})"}
        
        output, error, success = await conn.execute_command(cmd)
        
        if not success:
            return {"success": False, "message": f"SSH 执行失败: {error}"}
        
        # 分析输出
        output = output.strip()
        if action == "status":
            is_running = output == "active"
            return {"success": True, "message": f"Agent {agent.hostname} 状态: {'运行中' if is_running else '已停止'}", "output": output}
        else:
            return {"success": True, "message": f"Agent {agent.hostname} {action} 成功", "output": output}
            
    except Exception as e:
        return {"success": False, "message": f"控制 Agent 失败: {str(e)}"}

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
    
    result = await control_agent_process(agent, action)
    
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
    tasks = [control_agent_process(agent, action) for agent in agents]
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