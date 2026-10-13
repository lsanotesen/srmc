from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, WebSocket, WebSocketDisconnect, Form, Request, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from urllib.parse import quote
from models.app_service import AppService
from models.project import Project
from models.subsystem import Subsystem
from models.service_group import ServiceGroup
from schemas.service import ServiceCreate, ServiceUpdate, ServiceResponse, ServiceOperationResult
from schemas.common import ResponseModel
from utils.crypto import encrypt, decrypt
from utils.program_status import get_program_status
from services.audit_service import log_audit
from core.database import get_db
from api.dependencies import get_current_user, require_permission
from api.permission_dependencies import (
    assert_service_access,
    assert_services_access,
    assert_project_access,
    assert_high_risk_capability,
    assert_project_write_capability,
    get_visible_project_ids,
)
from utils.ssh_pool import ssh_pool
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment
from typing import List, Optional
import asyncio
import io
import json as _json
import uuid as _uuid
from datetime import datetime

router = APIRouter()

def expand_home_path(path: str) -> str:
    """将路径中的~展开为实际的家目录路径"""
    if path.startswith('~'):
        return f"$HOME{path[1:]}"
    return path

def get_script_path(script: str) -> str:
    """获取脚本路径，如果没有./前缀则自动添加，支持多行脚本"""
    if script.startswith('./') or script.startswith('/') or script.startswith('~'):
        return script
    return f"./{script}"

def format_script_command(script: str) -> str:
    """格式化脚本命令，支持多行脚本，将换行转换为 ; 连接（确保所有命令都执行）"""
    lines = script.strip().split('\n')
    formatted_lines = []
    for line in lines:
        line = line.strip()
        if line:
            # 如果是脚本文件名（不含空格）且没有路径前缀，添加 ./ 前缀
            if ' ' not in line and not line.startswith('./') and not line.startswith('/') and not line.startswith('~'):
                line = f"./{line}"
            formatted_lines.append(line)
    return '; '.join(formatted_lines)

async def try_agent_operation(service: AppService, action: str) -> Optional[dict]:
    from api.agent import manager
    from models.agent import Agent
    from core.database import SessionLocal
    
    db = SessionLocal()
    try:
        agent_uuid = service.agent_uuid
        deploy_type = service.deploy_type or service.service_type or 'HOST_APP'
        print(f"[Agent Op] action={action}, service_id={service.id}, deploy_type={deploy_type}, initial_agent_uuid={agent_uuid}")
        
        if not agent_uuid:
            agent = db.query(Agent).filter(
                Agent.ip == service.ip,
                Agent.status == 'online'
            ).first()
            if agent:
                agent_uuid = agent.uuid
                print(f"[Agent Op] Auto-selected agent {agent_uuid} for service {service.id} ({service.ip})")
            else:
                print(f"[Agent Op] No agent found for service {service.id} ({service.ip})")
                # 对于 Docker/Docker Compose 类型服务，没有 Agent 就无法操作
                if deploy_type in ('DOCKER', 'DOCKER_COMPOSE'):
                    return {"success": False, "message": f"没有在线的 Agent，无法控制 {deploy_type} 类型服务", "output": ""}
                return None
        else:
            online = manager.is_online(agent_uuid)
            print(f"[Agent Op] Agent {agent_uuid} online={online}")
            if not online:
                agent = db.query(Agent).filter(
                    Agent.ip == service.ip,
                    Agent.status == 'online'
                ).first()
                if agent:
                    agent_uuid = agent.uuid
                    print(f"[Agent Op] Original agent offline, auto-selected agent {agent_uuid} for service {service.id}")
                else:
                    print(f"[Agent Op] No online agent found for service {service.id} ({service.ip})")
                    # 对于 Docker/Docker Compose 类型服务，没有 Agent 就无法操作
                    if deploy_type in ('DOCKER', 'DOCKER_COMPOSE'):
                        return {"success": False, "message": f"没有在线的 Agent，无法控制 {deploy_type} 类型服务", "output": ""}
                    return None
        
        agent = db.query(Agent).filter(Agent.uuid == agent_uuid).first()
        
        if not agent:
            print(f"[Agent Op] Agent not found in DB: {agent_uuid}")
            return None
        
        print(f"[Agent Op] Agent IP check: service.ip={service.ip}, agent.ip={agent.ip}")
        if service.ip != agent.ip:
            print(f"[Agent Op] Service IP mismatch, skipping agent operation")
            return None
        
        print(f"[Agent Op] Sending command to agent {agent_uuid}, action={action}, deploy_type={deploy_type}...")
        
        # 根据部署类型设置超时时间
        # Docker Compose 操作可能需要更长时间（拉取镜像等）
        timeout = 60 if deploy_type in ('DOCKER', 'DOCKER_COMPOSE') else 30
        
        result = await manager.send_command_with_response(
            agent_uuid,
            str(service.id),
            action,
            service,
            timeout=timeout
        )
        print(f"[Agent Op] Command result: {result}")
        return result
    except asyncio.TimeoutError as e:
        print(f"[Agent Op] Command timeout: {e}")
        deploy_type = service.deploy_type or service.service_type or 'HOST_APP'
        return {"success": False, "message": f"命令执行超时({60 if deploy_type in ('DOCKER', 'DOCKER_COMPOSE') else 30}秒)", "output": ""}
    except Exception as e:
        print(f"[Agent Op] Agent operation failed: {e}")
        return {"success": False, "message": f"Agent 操作失败: {str(e)}", "output": ""}
    finally:
        db.close()

@router.get("/services/list", response_model=ResponseModel)
async def list_services(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    from services.data_scope_service import DataScopeService

    query = db.query(AppService)
    # DataScope 过滤：非管理员仅能查看有权限访问的项目下的服务
    if not DataScopeService._is_super_admin(user):
        visible_pids = DataScopeService.get_user_project_ids(db, user)
        query = query.filter(AppService.project_id.in_(visible_pids))
    services = query.all()
    result = []
    for service in services:
        project = db.query(Project).filter(Project.id == service.project_id).first()
        result.append({
            'id': service.id,
            'project_id': service.project_id,
            'project_name': project.name if project else None,
            'service_name': service.func_desc,
            'service_code': service.module,
            'service_type': service.service_type,
            'deploy_type': service.deploy_type,
            'container_name': service.container_name,
            'environment': 'production',
            'ip': service.ip,
            'status': 'UNKNOWN',
            'server_id': None,
            'owner': service.owner,
            'created_at': service.created_at,
            'updated_at': service.updated_at
        })
    return ResponseModel(data=result)

@router.get("/services", response_model=ResponseModel)
async def get_services(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    project_id: int = Query(None, ge=1),
    subsystem_id: int = Query(None, ge=1),
    group_id: int = Query(None, ge=1),
    deploy_type: str = Query(None),
    status: str = Query(None),
    agent_status: str = Query(None),
    func_desc: str = Query(None),
    module: str = Query(None),
    ip: str = Query(None),
    owner: str = Query(None),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    from models.subsystem import Subsystem
    from models.service_group import ServiceGroup
    from sqlalchemy import func
    from utils.cache import get_cached, set_cached
    from services.data_scope_service import DataScopeService
    import hashlib

    # 构建 DB 层过滤条件（status/agent_status 不在 DB 中，后置 Redis 过滤）
    filters = []
    if project_id:
        filters.append(AppService.project_id == project_id)
    if subsystem_id:
        filters.append(AppService.subsystem_id == subsystem_id)
    if group_id:
        filters.append(AppService.group_id == group_id)
    if deploy_type:
        filters.append(AppService.deploy_type == deploy_type)
    if func_desc:
        filters.append(AppService.func_desc.like(f"%{func_desc}%"))
    if module:
        filters.append(AppService.module.like(f"%{module}%"))
    if ip:
        filters.append(AppService.ip.like(f"%{ip}%"))
    if owner:
        filters.append(AppService.owner.like(f"%{owner}%"))

    # DataScope 权限过滤：非 ADMIN 只能看有权限的项目
    if not DataScopeService._is_super_admin(user):
        visible_pids = DataScopeService.get_user_project_ids(db, user)
        filters.append(AppService.project_id.in_(visible_pids))
        # 可见范围签名：避免不同可见范围的用户共享同一份 Redis 列表缓存（缓存污染）
        scope_key = hashlib.md5(
            ",".join(str(p) for p in sorted(visible_pids)).encode()
        ).hexdigest()
    else:
        scope_key = "all"

    has_runtime_filter = bool(status or agent_status)

    if has_runtime_filter:
        # ---- 有运行时状态筛选，跳过 Redis 列表缓存 ----
        # 状态不在 DB 中，必须先查全量 + Redis 过滤再分页
        base_query = db.query(AppService).filter(*filters)
        all_services = base_query.all()
        if not all_services:
            return ResponseModel(data={"items": [], "total": 0, "page": page, "size": size})

        # Redis 批量取状态
        try:
            from utils.redis_client import redis_client
            service_ids = [s.id for s in all_services]
            status_keys = [f"service_status:{sid}" for sid in service_ids]
            source_keys = [f"service_status_source:{sid}" for sid in service_ids]
            # 【新增】批量获取时间字段
            time_keys = [f"status_last_seen_at:{sid}" for sid in service_ids]
            stopped_keys = [f"stopped_at:{sid}" for sid in service_ids]
            
            status_values = redis_client.mget(status_keys)
            source_values = redis_client.mget(source_keys)
            # 【新增】批量获取时间值
            time_values = redis_client.mget(time_keys)
            stopped_values = redis_client.mget(stopped_keys)

            # 预查 Agent 在线状态（与 count 接口口径一致：有 agent_uuid 且 Agent 在线才算在线）
            from models.agent import Agent
            from datetime import datetime, timedelta
            agent_uuids = list({s.agent_uuid for s in all_services if s.agent_uuid})
            online_uuids = set()
            try:
                from api.agent import manager
            except Exception:
                manager = None
            if agent_uuids:
                for a in db.query(Agent).filter(Agent.uuid.in_(agent_uuids)).all():
                    is_online = False
                    if manager is not None:
                        try:
                            is_online = manager.is_online(a.uuid)
                        except Exception:
                            is_online = False
                    if not is_online and a.last_heartbeat:
                        # 软在线：30s 内有心跳
                        try:
                            is_online = datetime.now() - a.last_heartbeat < timedelta(seconds=30)
                        except Exception:
                            is_online = False
                    if is_online:
                        online_uuids.add(a.uuid)

            enriched = []
            for i, svc in enumerate(all_services):
                raw_s = status_values[i]
                st = (raw_s.decode() if raw_s and isinstance(raw_s, bytes) else (raw_s or "UNKNOWN")).upper()
                raw_src = source_values[i]
                src = raw_src.decode() if raw_src and isinstance(raw_src, bytes) else (raw_src or "")
                # 【新增】处理时间字段，统一转换为Unix时间戳整数
                raw_time = time_values[i]
                status_last_seen_at = int(raw_time) if raw_time else None
                raw_stopped = stopped_values[i]
                stopped_at = int(raw_stopped) if raw_stopped else None
                
                # Agent 在线：服务关联了 agent_uuid 且该 Agent 当前在线
                agent_online = bool(svc.agent_uuid) and (svc.agent_uuid in online_uuids) and src != 'OFFLINE'
                enriched.append((svc, st, src, agent_online, status_last_seen_at, stopped_at))
        except Exception as e:
            print(f"Redis status lookup error (non-critical): {e}")
            enriched = [(s, "UNKNOWN", "", False) for s in all_services]

        # 内存过滤 status / agent_status
        if status:
            target = status.upper()
            if target == 'UNKNOWN':
                # “状态未知”桶：真正未知/异常态（UNKNOWN / PARTIAL 等），
                # 不含 INACTIVE（未启用/停止）与 COMPLETED（一次性任务已完成）——它们是预期状态
                enriched = [x for x in enriched
                            if x[1] not in ('RUNNING', 'STOPPED', 'INACTIVE', 'COMPLETED')]
            elif target == 'INACTIVE':
                # “未启用/停止”桶：含一次性任务已完成（同为预期终态）
                enriched = [x for x in enriched if x[1] in ('INACTIVE', 'COMPLETED')]
            else:
                enriched = [x for x in enriched if x[1] == target]
        if agent_status:
            want_online = agent_status.lower() == 'online'
            if want_online:
                # 在线：agent_online 为 True
                enriched = [x for x in enriched if x[3]]
            else:
                # 离线(Agent异常)：已关联 agent_uuid 但 Agent 离线；不含从未关联 Agent 的服务
                enriched = [x for x in enriched if x[0].agent_uuid and not x[3]]

        total = len(enriched)
        start = (page - 1) * size
        page_slice = enriched[start:start + size]
        page_ids = [x[0].id for x in page_slice]

        if not page_ids:
            return ResponseModel(data={"items": [], "total": total, "page": page, "size": size})

        # 对分页后的 ID 做 JOIN 查询返回完整字段
        results = db.query(AppService, Project, Subsystem, ServiceGroup).\
            outerjoin(Project, AppService.project_id == Project.id).\
            outerjoin(Subsystem, AppService.subsystem_id == Subsystem.id).\
            outerjoin(ServiceGroup, AppService.group_id == ServiceGroup.id).\
            filter(AppService.id.in_(page_ids)).all()

        id_to_row = {s.id: (s, p, sub, grp) for s, p, sub, grp in results}
        status_by_id = {svc.id: (st, src, agent_online, status_last_seen_at, stopped_at) for svc, st, src, agent_online, status_last_seen_at, stopped_at in enriched}

        result = []
        for svc_id in page_ids:
            if svc_id not in id_to_row:
                continue
            svc, project, subsystem, srv_group = id_to_row[svc_id]
            st, src, agent_online, status_last_seen_at, stopped_at = status_by_id.get(svc_id, ("UNKNOWN", "", False, None, None))
            result.append({
                'id': svc.id,
                'project_id': svc.project_id,
                'project_name': project.name if project else None,
                'subsystem_id': svc.subsystem_id,
                'subsystem_name': subsystem.subsystem_name if subsystem else None,
                'group_id': svc.group_id,
                'group_name': srv_group.group_name if srv_group else None,
                'func_desc': svc.func_desc,
                'module': svc.module,
                'ip': svc.ip,
                'ssh_port': svc.ssh_port,
                'username': svc.username,
                'program_path': svc.program_path,
                'start_script': svc.start_script,
                'stop_script': svc.stop_script,
                'log_path': svc.log_path,
                'port': svc.port,
                'owner': svc.owner,
                'remark': svc.remark,
                'service_type': svc.service_type,
                'deploy_type': svc.deploy_type,
                'container_name': svc.container_name,
                'image_name': svc.image_name,
                'image_tag': svc.image_tag,
                'container_id': svc.container_id,
                'port_mapping': svc.port_mapping,
                'volume_mapping': svc.volume_mapping,
                'network_mode': svc.network_mode,
                'log_type': svc.log_type,
                'agent_uuid': svc.agent_uuid,
                'created_at': svc.created_at,
                'updated_at': svc.updated_at,
                'status': st,
                'status_source': src,
                'agent_status': 'online' if agent_online else 'offline',
                # 【新增】时间字段
                'status_last_seen_at': status_last_seen_at,
                'stopped_at': stopped_at,
            })

        return ResponseModel(data={"items": result, "total": total, "page": page, "size": size})

    # ---- 无运行时状态筛选，走原有缓存路径 ----
    filter_str = f"{scope_key}:{project_id or 0}:{subsystem_id or 0}:{group_id or 0}:{deploy_type or ''}:{func_desc or ''}:{module or ''}:{ip or ''}:{owner or ''}:{page}:{size}"
    cache_key = f"services_list:{hashlib.md5(filter_str.encode()).hexdigest()}"

    cached = get_cached(cache_key)
    if cached is not None:
        result = cached.get('items', [])
        total = cached.get('total', 0)
    else:
        count_query = db.query(func.count(AppService.id))
        if filters:
            count_query = count_query.filter(*filters)
        total = count_query.scalar()

        query = db.query(AppService, Project, Subsystem, ServiceGroup).\
            outerjoin(Project, AppService.project_id == Project.id).\
            outerjoin(Subsystem, AppService.subsystem_id == Subsystem.id).\
            outerjoin(ServiceGroup, AppService.group_id == ServiceGroup.id)

        if filters:
            query = query.filter(*filters)

        results = query.offset((page - 1) * size).limit(size).all()

        result = []
        for service, project, subsystem, service_group in results:
            result.append({
                'id': service.id,
                'project_id': service.project_id,
                'project_name': project.name if project else None,
                'subsystem_id': service.subsystem_id,
                'subsystem_name': subsystem.subsystem_name if subsystem else None,
                'group_id': service.group_id,
                'group_name': service_group.group_name if service_group else None,
                'func_desc': service.func_desc,
                'module': service.module,
                'ip': service.ip,
                'ssh_port': service.ssh_port,
                'username': service.username,
                'program_path': service.program_path,
                'start_script': service.start_script,
                'stop_script': service.stop_script,
                'log_path': service.log_path,
                'port': service.port,
                'owner': service.owner,
                'remark': service.remark,
                'service_type': service.service_type,
                'deploy_type': service.deploy_type,
                'container_name': service.container_name,
                'image_name': service.image_name,
                'image_tag': service.image_tag,
                'container_id': service.container_id,
                'port_mapping': service.port_mapping,
                'volume_mapping': service.volume_mapping,
                'network_mode': service.network_mode,
                'log_type': service.log_type,
                'agent_uuid': service.agent_uuid,
                'created_at': service.created_at,
                'updated_at': service.updated_at,
                'status': 'UNKNOWN',
                'status_source': '',
                'agent_status': 'offline'
            })

    # 实时从 Redis 获取服务状态
    try:
        from utils.redis_client import redis_client
        if redis_client:
            service_ids = [s['id'] for s in result]
            print(f"Service IDs: {service_ids}")
            if service_ids:
                status_keys = [f"service_status:{sid}" for sid in service_ids]
                source_keys = [f"service_status_source:{sid}" for sid in service_ids]
                time_keys = [f"status_last_seen_at:{sid}" for sid in service_ids]
                stopped_keys = [f"stopped_at:{sid}" for sid in service_ids]
                status_values = redis_client.mget(status_keys)
                source_values = redis_client.mget(source_keys)
                time_values = redis_client.mget(time_keys)
                stopped_values = redis_client.mget(stopped_keys)
                print(f"Redis values count - status: {len(status_values) if status_values else 0}, time: {len(time_values) if time_values else 0}")

            for i, service in enumerate(result):
                print(f"Processing service {i}: ID={service.get('id')}, agent_uuid={service.get('agent_uuid')}")
                cached_status = status_values[i] if status_values else None
                cached_source = source_values[i] if source_values else None
                raw_time = time_values[i] if time_values else None
                raw_stopped = stopped_values[i] if stopped_values else None
                
                if cached_status:
                    service['status'] = cached_status.decode() if isinstance(cached_status, bytes) else cached_status
                    service['status_source'] = cached_source.decode() if cached_source and isinstance(cached_source, bytes) else (cached_source or 'AGENT')
                    service['agent_status'] = 'online'
                    # 【新增】处理时间字段，转换为整数 Unix 秒
                    service['status_last_seen_at'] = int(raw_time) if raw_time else None
                    service['stopped_at'] = int(raw_stopped) if raw_stopped else None
                else:
                    service['status'] = 'UNKNOWN'
                    service['status_source'] = ''
                    service['agent_status'] = 'offline'
                    # 【新增】时间字段设为null
                    service['status_last_seen_at'] = None
                    service['stopped_at'] = None
    except Exception as e:
        print(f"Redis status lookup error (non-critical): {e}")
        print(f"Redis connection: {redis_client is not None}")
        print(f"Service count: {len(result)}")
        if result and hasattr(result[0], 'id'):
            print(f"First service ID: {result[0].id}")
        import traceback
        traceback.print_exc()

    # 构建缓存数据（不含实时状态字段）
    cache_items = []
    for item in result:
        cache_item = {k: v for k, v in item.items() if k not in ('status', 'status_source', 'agent_status')}
        cache_items.append(cache_item)

    set_cached(cache_key, {"items": cache_items, "total": total, "page": page, "size": size}, ttl=30)

    response_data = {"items": result, "total": total, "page": page, "size": size}
    
    # 【新增】详细的调试信息
    print(f"=== API Response Debug ===")
    print(f"Total services: {total}")
    print(f"Returning items: {len(result)}")
    
    if result:
        print(f"Service details:")
        for i, service in enumerate(result[:5]):  # 显示前5个服务
            print(f"  Service {i}: ID={service.get('id')}, Name={service.get('func_desc', 'N/A')}")
            print(f"    Status: {service.get('status')}")
            print(f"    Status Last Seen At: {service.get('status_last_seen_at')}")
            print(f"    Stopped At: {service.get('stopped_at')}")
            print(f"    Has Time Fields: {'status_last_seen_at' in service and 'stopped_at' in service}")
            print()
    
    return ResponseModel(data=response_data)

@router.get("/services/count", response_model=ResponseModel)
async def count_services(
    project_id: int = Query(None, ge=1),
    subsystem_id: int = Query(None, ge=1),
    group_id: int = Query(None, ge=1),
    deploy_type: str = Query(None),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    from services.data_scope_service import DataScopeService

    query = db.query(AppService)

    # DataScope 权限过滤
    if not DataScopeService._is_super_admin(user):
        visible_pids = DataScopeService.get_user_project_ids(db, user)
        query = query.filter(AppService.project_id.in_(visible_pids))

    if project_id:
        query = query.filter(AppService.project_id == project_id)
    if subsystem_id:
        query = query.filter(AppService.subsystem_id == subsystem_id)
    if group_id:
        query = query.filter(AppService.group_id == group_id)
    if deploy_type:
        query = query.filter(AppService.deploy_type == deploy_type)

    # 只取统计需要的列（id / agent_uuid），避免加载整行 ORM 对象。
    # 该接口在每次切换项目/子系统时都会被调用，全字段加载会明显拖慢切换。
    services = query.with_entities(AppService.id, AppService.agent_uuid).all()
    total = len(services)

    # Redis 批量取状态做分布统计
    running = stopped = unknown = inactive = agent_offline = 0
    if services:
        try:
            from utils.redis_client import redis_client
            service_ids = [sid for sid, _ in services]
            status_keys = [f"service_status:{sid}" for sid in service_ids]
            source_keys = [f"service_status_source:{sid}" for sid in service_ids]
            status_vals = redis_client.mget(status_keys)
            source_vals = redis_client.mget(source_keys)

            # 预查 Agent 在线状态（与列表筛选口径一致）
            from models.agent import Agent
            from datetime import datetime as _dt, timedelta as _td
            agent_uuids = list({uuid for _, uuid in services if uuid})
            online_uuids = set()
            try:
                from api.agent import manager as _mgr
            except Exception:
                _mgr = None
            if agent_uuids:
                for a in db.query(Agent).filter(Agent.uuid.in_(agent_uuids)).all():
                    is_online = False
                    if _mgr is not None:
                        try:
                            is_online = _mgr.is_online(a.uuid, a.last_heartbeat)
                        except Exception:
                            is_online = False
                    if not is_online and a.last_heartbeat:
                        try:
                            is_online = _dt.now() - a.last_heartbeat < _td(seconds=30)
                        except Exception:
                            is_online = False
                    if is_online:
                        online_uuids.add(a.uuid)

            for i, (svc_id, svc_agent_uuid) in enumerate(services):
                raw_s = status_vals[i]
                st = raw_s.decode().upper() if raw_s and isinstance(raw_s, bytes) else (raw_s or "UNKNOWN").upper()
                raw_src = source_vals[i]
                src = raw_src.decode() if raw_src and isinstance(raw_src, bytes) else (raw_src or "")

                if st == "RUNNING":
                    running += 1
                elif st == "STOPPED":
                    stopped += 1
                elif st in ("INACTIVE", "COMPLETED"):
                    # 未启用/停止 与 一次性任务已完成 都是预期状态，不计入异常/未知
                    inactive += 1
                else:
                    unknown += 1

                # Agent 异常：服务关联了 agent_uuid，但该 Agent 当前离线（含 source=OFFLINE）
                if svc_agent_uuid:
                    agent_online = (svc_agent_uuid in online_uuids) and src != 'OFFLINE'
                    if not agent_online:
                        agent_offline += 1
        except Exception as e:
            print(f"[services/count] Redis status aggregation failed: {e}")

    return ResponseModel(data={
        "total": total,
        "running": running,
        "stopped": stopped,
        "inactive": inactive,
        "agentOffline": agent_offline,
        "unknown": unknown,
    })

@router.get("/services/template")
async def download_service_template(
    user = Depends(require_permission("service_manage"))
):
    """下载服务导入模板"""
    headers = [
        '功能描述', '对应模块', 'IP地址', 'SSH端口', '用户名', '密码',
        '程序路径', '启动脚本', '停止脚本', '日志路径', '端口', '部署方式',
        '容器名称', '镜像名称', '端口映射', '日志类型', '责任人', '备注'
    ]
    
    wb = Workbook()
    ws = wb.active
    ws.title = "服务导入模板"
    
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
    
    ws.cell(row=1, column=12).comment = Comment("请从下拉框选择：主机部署 / Docker容器 / Docker Compose", "系统提示")
    
    ws.append([
        '示例主机服务', '预处理模块', '192.168.1.100', '22', 'root', 'password',
        '/opt/service/', '/opt/service/start.sh', '/opt/service/stop.sh', '/var/log/service/', '8080', '主机部署',
        '', '', '', '', '张三', '主机部署需要填写启动和停止脚本'
    ])
    
    ws.append([
        '示例Docker容器服务', 'Web服务', '192.168.1.101', '22', 'root', 'password',
        '/opt/nginx/', '', '', '/var/log/nginx/', '80', 'Docker容器',
        'nginx-web', 'nginx:1.25', '80:80', 'HOST_DIR', '李四', '单容器部署，系统自动使用docker start/stop管理'
    ])
    
    ws.append([
        '示例Docker Compose服务', '完整应用', '192.168.1.102', '22', 'root', 'password',
        '/opt/docker-app/', '', '', '/var/log/docker-app/', '8080', 'Docker Compose',
        '', '', '', 'DOCKER_LOGS', '王五', 'docker-compose部署，系统自动使用docker-compose up -d/down管理多个容器'
    ])
    
    # 设置部署方式列的下拉框（第12列，从第2行开始）
    dv = DataValidation(
        type="list",
        formula1='"主机部署,Docker容器,Docker Compose"',
        allow_blank=False
    )
    ws.add_data_validation(dv)
    # 应用到第12列（部署方式）的所有数据行
    dv.add(f"L2:L100")
    
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=service_import_template.xlsx"}
    )


@router.get("/services/export")
async def export_services(
    project_id: int = Query(None, ge=1),
    subsystem_id: int = Query(None, ge=1),
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_manage"))
):
    """导出服务列表，按程序分类和部署方式分Sheet"""
    from models.service_group import ServiceGroup
    
    query = db.query(AppService, Project, ServiceGroup).outerjoin(Project, AppService.project_id == Project.id).outerjoin(ServiceGroup, AppService.group_id == ServiceGroup.id)
    if project_id:
        query = query.filter(AppService.project_id == project_id)
    if subsystem_id:
        query = query.filter(AppService.subsystem_id == subsystem_id)
    
    results = query.all()
    
    # 部署方式映射
    deploy_type_map = {
        'HOST': '主机部署',
        'DOCKER': 'Docker容器',
        'DOCKER_COMPOSE': 'Docker Compose'
    }
    
    # 主机部署字段列表
    host_headers = [
        '功能描述', '对应模块', 'IP地址', 'SSH端口', '用户名', '密码',
        '程序路径', '启动脚本', '停止脚本', '日志路径', '端口', '部署方式', '责任人', '备注'
    ]
    
    docker_container_headers = [
        '功能描述', '对应模块', 'IP地址', 'SSH端口', '用户名', '密码',
        '程序路径', '日志路径', '端口', '部署方式',
        '容器名称', '镜像名称', '端口映射', '日志类型', '责任人', '备注'
    ]
    
    docker_compose_headers = [
        '功能描述', '对应模块', 'IP地址', 'SSH端口', '用户名', '密码',
        '程序路径', '日志路径', '端口', '部署方式', '日志类型', '责任人', '备注'
    ]
    
    # 按程序分类和部署方式分组
    grouped_services = {}
    project_name = ""
    subsystem_name = ""
    
    for service, project, group in results:
        if project and not project_name:
            project_name = project.name
        if service.subsystem_id and not subsystem_name:
            subsystem = db.query(Subsystem).filter(Subsystem.id == service.subsystem_id).first()
            if subsystem:
                subsystem_name = subsystem.subsystem_name
        
        group_name = group.group_name if group else '未分类'
        deploy_type = service.deploy_type or 'HOST'
        
        key = (group_name, deploy_type)
        if key not in grouped_services:
            grouped_services[key] = []
        grouped_services[key].append(service)
    
    wb = Workbook()
    
    # 表头样式
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    
    # 如果没有数据，创建一个空的sheet
    if not grouped_services:
        ws = wb.active
        ws.title = "服务列表"
        for col, header in enumerate(host_headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
    else:
        # 为每个程序分类和部署方式创建一个Sheet
        for (group_name, deploy_type), services in grouped_services.items():
            # 创建Sheet名称（不包含部署方式后缀）
            sheet_name = group_name[:31]
            ws = wb.create_sheet(title=sheet_name)
            
            # 根据部署方式选择表头
            if deploy_type == 'HOST':
                headers = host_headers
            elif deploy_type == 'DOCKER':
                headers = docker_container_headers
            else:
                headers = docker_compose_headers
            
            # 写入表头
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.fill = header_fill
                cell.font = header_font
            
            # 写入数据
            for row_idx, service in enumerate(services, 2):
                ws.cell(row=row_idx, column=1, value=service.func_desc)
                ws.cell(row=row_idx, column=2, value=service.module or '')
                ws.cell(row=row_idx, column=3, value=service.ip)
                ws.cell(row=row_idx, column=4, value=service.ssh_port or 22)
                ws.cell(row=row_idx, column=5, value=service.username)
                ws.cell(row=row_idx, column=6, value=decrypt(service.password) if service.password else '')
                ws.cell(row=row_idx, column=7, value=service.program_path or '')
                
                if deploy_type == 'HOST':
                    ws.cell(row=row_idx, column=8, value=service.start_script or '')
                    ws.cell(row=row_idx, column=9, value=service.stop_script or '')
                    ws.cell(row=row_idx, column=10, value=service.log_path or '')
                    ws.cell(row=row_idx, column=11, value=service.port or '')
                    ws.cell(row=row_idx, column=12, value=deploy_type_map.get(service.deploy_type, service.deploy_type) or '')
                    ws.cell(row=row_idx, column=13, value=service.owner or '')
                    ws.cell(row=row_idx, column=14, value=service.remark or '')
                elif deploy_type == 'DOCKER':
                    ws.cell(row=row_idx, column=8, value=service.log_path or '')
                    ws.cell(row=row_idx, column=9, value=service.port or '')
                    ws.cell(row=row_idx, column=10, value=deploy_type_map.get(service.deploy_type, service.deploy_type) or '')
                    ws.cell(row=row_idx, column=11, value=service.container_name or '')
                    ws.cell(row=row_idx, column=12, value=service.image_name or '')
                    ws.cell(row=row_idx, column=13, value=service.port_mapping or '')
                    ws.cell(row=row_idx, column=14, value=service.log_type or '')
                    ws.cell(row=row_idx, column=15, value=service.owner or '')
                    ws.cell(row=row_idx, column=16, value=service.remark or '')
                else:
                    ws.cell(row=row_idx, column=8, value=service.log_path or '')
                    ws.cell(row=row_idx, column=9, value=service.port or '')
                    ws.cell(row=row_idx, column=10, value=deploy_type_map.get(service.deploy_type, service.deploy_type) or '')
                    ws.cell(row=row_idx, column=11, value=service.log_type or '')
                    ws.cell(row=row_idx, column=12, value=service.owner or '')
                    ws.cell(row=row_idx, column=13, value=service.remark or '')
        
        # 删除默认创建的空sheet（名为'Sheet'或'服务列表'）
        if 'Sheet' in wb.sheetnames:
            del wb['Sheet']
        elif '服务列表' in wb.sheetnames:
            del wb['服务列表']
    
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    # 生成文件名：{项目名}-{子系统名}_服务列表.xlsx
    filename_parts = []
    if project_name:
        filename_parts.append(project_name)
    if subsystem_name:
        filename_parts.append(subsystem_name)
    filename_parts.append("服务列表")
    
    filename = quote("-".join(filename_parts) + ".xlsx")
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}; filename*=UTF-8''{filename}"}
    )


@router.get("/services/{service_id}", response_model=ResponseModel)
async def get_service(
    service_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    from models.subsystem import Subsystem
    from models.service_group import ServiceGroup
    
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    # DataScope：只能查看有权限项目下的服务
    assert_service_access(db, user, service_id, service=service)

    project = db.query(Project).filter(Project.id == service.project_id).first()
    subsystem = db.query(Subsystem).filter(Subsystem.id == service.subsystem_id).first() if service.subsystem_id else None
    service_group = db.query(ServiceGroup).filter(ServiceGroup.id == service.group_id).first() if service.group_id else None

    # 从 Redis 读取当前状态和容器详情（用于 Docker Compose 服务的容器列表展示）
    import json
    from utils.redis_client import redis_client
    from models.service_container_config import ServiceContainerConfig
    import services.container_status_service as container_status_service
    current_status = None
    status_source = None
    containers = []
    try:
        status_bytes = redis_client.get(f"service_status:{service_id}")
        if status_bytes:
            current_status = status_bytes.decode('utf-8') if isinstance(status_bytes, bytes) else status_bytes
        source_bytes = redis_client.get(f"service_status_source:{service_id}")
        if source_bytes:
            status_source = source_bytes.decode('utf-8') if isinstance(source_bytes, bytes) else source_bytes
        containers_bytes = redis_client.get(f"service_containers:{service_id}")
        if containers_bytes:
            containers_str = containers_bytes.decode('utf-8') if isinstance(containers_bytes, bytes) else containers_bytes
            containers = json.loads(containers_str)
    except Exception as e:
        print(f"Get service status error: {e}")

    # 为每个容器附加运行类型与业务状态，供前端直接展示（前端不再自行判断异常）
    # 运行类型解析优先级：容器级配置 → 服务级默认('*') → permanent
    run_mode_map = {}
    try:
        rows = (
            db.query(ServiceContainerConfig)
            .filter(ServiceContainerConfig.service_id == service_id)
            .all()
        )
        run_mode_map = {r.container_name: r.run_mode for r in rows}
    except Exception as e:
        print(f"Load container run_mode error: {e}")

    service_run_mode = container_status_service.resolve_run_mode(
        run_mode_map, container_status_service.SERVICE_LEVEL_KEY
    )

    if containers:
        for c in containers:
            mode = container_status_service.resolve_run_mode(run_mode_map, c.get('name'))
            c['run_mode'] = mode
            c['biz_status'] = container_status_service.compute_container_status(c, mode)

    return ResponseModel(data={
        'id': service.id,
        'project_id': service.project_id,
        'project_name': project.name if project else None,
        'subsystem_id': service.subsystem_id,
        'subsystem_name': subsystem.subsystem_name if subsystem else None,
        'group_id': service.group_id,
        'group_name': service_group.group_name if service_group else None,
        'func_desc': service.func_desc,
        'module': service.module,
        'ip': service.ip,
        'ssh_port': service.ssh_port,
        'username': service.username,
        'program_path': service.program_path,
        'start_script': service.start_script,
        'stop_script': service.stop_script,
        'log_path': service.log_path,
        'port': service.port,
        'owner': service.owner,
        'remark': service.remark,
        # 新增字段
        'service_type': service.service_type,
        'deploy_type': service.deploy_type,
        'container_name': service.container_name,
        'image_name': service.image_name,
        'image_tag': service.image_tag,
        'container_id': service.container_id,
        'port_mapping': service.port_mapping,
        'volume_mapping': service.volume_mapping,
        'network_mode': service.network_mode,
        'log_type': service.log_type,
        'agent_uuid': service.agent_uuid,
        'created_at': service.created_at,
        'updated_at': service.updated_at,
        # 运行时状态
        'current_status': current_status,
        'status_source': status_source,
        'containers': containers,
        # 服务级默认运行类型（物理机服务无容器，只能用它；容器级配置优先）
        'service_run_mode': service_run_mode,
    })

@router.post("/services", response_model=ResponseModel)
async def create_service(
    service_create: ServiceCreate,
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_manage"))
):
    from models.subsystem import Subsystem
    from models.service_group import ServiceGroup
    
    project = db.query(Project).filter(Project.id == service_create.project_id).first()
    if not project:
        raise HTTPException(status_code=400, detail="项目不存在")

    # DataScope：只能向有权限的项目创建服务；发布/创建属高风险，需项目共享独立授权
    assert_project_access(db, user, service_create.project_id)
    assert_high_risk_capability(db, user, service_create.project_id, "deploy")

    if service_create.subsystem_id:
        subsystem = db.query(Subsystem).filter(Subsystem.id == service_create.subsystem_id).first()
        if not subsystem:
            raise HTTPException(status_code=400, detail="子系统不存在")
    
    if service_create.group_id:
        service_group = db.query(ServiceGroup).filter(ServiceGroup.id == service_create.group_id).first()
        if not service_group:
            raise HTTPException(status_code=400, detail="程序分类不存在")
    
    new_service = AppService(
        project_id=service_create.project_id,
        subsystem_id=service_create.subsystem_id,
        group_id=service_create.group_id,
        func_desc=service_create.func_desc,
        module=service_create.module,
        ip=str(service_create.ip),
        ssh_port=service_create.ssh_port or 22,
        username=service_create.username,
        password=encrypt(service_create.password),
        program_path=service_create.program_path,
        start_script=service_create.start_script,
        stop_script=service_create.stop_script,
        log_path=service_create.log_path,
        log_type=service_create.log_type,
        port=service_create.port,
        owner=service_create.owner,
        remark=service_create.remark,
        service_type=service_create.service_type or 'HOST_APP',
        deploy_type=service_create.deploy_type or 'HOST',
        container_name=service_create.container_name,
        image_name=service_create.image_name,
        port_mapping=service_create.port_mapping,
        volume_mapping=service_create.volume_mapping,
        network_mode=service_create.network_mode,
        image_tag=service_create.image_tag,
        agent_uuid=service_create.agent_uuid
    )
    
    db.add(new_service)
    db.commit()

    # 清除服务列表缓存
    from utils.cache import invalidate_services_list
    invalidate_services_list()

    from models.agent import Agent
    online_agent = db.query(Agent).filter(
        Agent.ip == new_service.ip,
        Agent.status == 'online'
    ).first()

    if online_agent:
        new_service.agent_uuid = online_agent.uuid
        db.commit()
        invalidate_services_list()
        print(f"Auto-associated service {new_service.id} to agent {online_agent.uuid}")
        
        from api.agent import manager
        if manager.is_online(online_agent.uuid):
            import json
            from datetime import datetime
            pull_message = {
                "type": "pull_services",
                "request_id": "",
                "timestamp": datetime.now().timestamp(),
                "data": {}
            }
            await manager.send_message(online_agent.uuid, pull_message)
            print(f"Sent pull_services to agent {online_agent.uuid}")
    
    log_audit(db, user.id, user.username, "SERVICE_CREATE", 
              service_id=new_service.id,
              project_id=new_service.project_id,
              subsystem_id=new_service.subsystem_id,
              result="success", output=f"创建服务: {service_create.func_desc}")
    
    return ResponseModel(data={
        'id': new_service.id,
        'project_id': new_service.project_id,
        'project_name': project.name,
        'subsystem_id': new_service.subsystem_id,
        'group_id': new_service.group_id,
        'func_desc': new_service.func_desc,
        'module': new_service.module,
        'ip': new_service.ip,
        'ssh_port': new_service.ssh_port,
        'username': new_service.username,
        'program_path': new_service.program_path,
        'start_script': new_service.start_script,
        'stop_script': new_service.stop_script,
        'log_path': new_service.log_path,
        'port': new_service.port,
        'owner': new_service.owner,
        'remark': new_service.remark,
        'status': None,
        'service_type': new_service.service_type,
        'deploy_type': new_service.deploy_type,
        'container_name': new_service.container_name,
        'image_name': new_service.image_name,
        'image_tag': new_service.image_tag,
        'container_id': new_service.container_id,
        'port_mapping': new_service.port_mapping,
        'volume_mapping': new_service.volume_mapping,
        'network_mode': new_service.network_mode,
        'log_type': new_service.log_type,
        'agent_uuid': new_service.agent_uuid,
        'created_at': new_service.created_at,
        'updated_at': new_service.updated_at
    })

@router.put("/services/{service_id}", response_model=ResponseModel)
async def update_service(
    service_id: int,
    service_update: ServiceUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_manage"))
):
    from models.subsystem import Subsystem
    from models.service_group import ServiceGroup
    
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    # DataScope：只能修改有权限项目下的服务
    assert_service_access(db, user, service_id, service=service)
    # 项目写操作：只读共享不得修改服务配置
    assert_project_write_capability(db, user, service.project_id)

    if service_update.project_id is not None:
        project = db.query(Project).filter(Project.id == service_update.project_id).first()
        if not project:
            raise HTTPException(status_code=400, detail="项目不存在")
        # DataScope：不允许把服务改挂到无权限的项目
        assert_project_access(db, user, service_update.project_id)
        service.project_id = service_update.project_id
    
    if service_update.subsystem_id is not None:
        if service_update.subsystem_id:
            subsystem = db.query(Subsystem).filter(Subsystem.id == service_update.subsystem_id).first()
            if not subsystem:
                raise HTTPException(status_code=400, detail="子系统不存在")
        service.subsystem_id = service_update.subsystem_id
    
    if service_update.group_id is not None:
        if service_update.group_id:
            service_group = db.query(ServiceGroup).filter(ServiceGroup.id == service_update.group_id).first()
            if not service_group:
                raise HTTPException(status_code=400, detail="程序分类不存在")
        service.group_id = service_update.group_id
    
    if service_update.func_desc is not None:
        service.func_desc = service_update.func_desc
    if service_update.module is not None:
        service.module = service_update.module
    if service_update.ip is not None:
        service.ip = str(service_update.ip)
    if service_update.ssh_port is not None:
        service.ssh_port = service_update.ssh_port
    if service_update.username is not None:
        service.username = service_update.username
    if service_update.password:
        service.password = encrypt(service_update.password)
    if service_update.program_path is not None:
        service.program_path = service_update.program_path
    if service_update.start_script is not None:
        service.start_script = service_update.start_script
    if service_update.stop_script is not None:
        service.stop_script = service_update.stop_script
    if service_update.log_path is not None:
        service.log_path = service_update.log_path
    if service_update.port is not None:
        service.port = service_update.port
    if service_update.owner is not None:
        service.owner = service_update.owner
    if service_update.remark is not None:
        service.remark = service_update.remark
    # Docker相关字段
    if service_update.deploy_type is not None:
        service.deploy_type = service_update.deploy_type
    if service_update.service_type is not None:
        service.service_type = service_update.service_type
    if service_update.container_name is not None:
        service.container_name = service_update.container_name
    if service_update.image_name is not None:
        service.image_name = service_update.image_name
    if service_update.image_tag is not None:
        service.image_tag = service_update.image_tag
    if service_update.port_mapping is not None:
        service.port_mapping = service_update.port_mapping
    if service_update.volume_mapping is not None:
        service.volume_mapping = service_update.volume_mapping
    if service_update.network_mode is not None:
        service.network_mode = service_update.network_mode
    if service_update.agent_uuid is not None:
        service.agent_uuid = service_update.agent_uuid
    if service_update.log_type is not None:
        service.log_type = service_update.log_type

    db.commit()

    # 清除服务列表缓存
    from utils.cache import invalidate_services_list
    invalidate_services_list()

    # 通知关联的在线 Agent 刷新服务列表（覆盖更新、路径变更等场景）
    await notify_agents_pull_services(db, service.agent_uuid)

    project = db.query(Project).filter(Project.id == service.project_id).first()
    subsystem = db.query(Subsystem).filter(Subsystem.id == service.subsystem_id).first() if service.subsystem_id else None
    service_group = db.query(ServiceGroup).filter(ServiceGroup.id == service.group_id).first() if service.group_id else None
    
    log_audit(db, user.id, user.username, "SERVICE_UPDATE", 
              service_id=service.id,
              project_id=service.project_id,
              subsystem_id=service.subsystem_id,
              result="success", output=f"更新服务: {service.func_desc}")
    
    return ResponseModel(data={
        'id': service.id,
        'project_id': service.project_id,
        'project_name': project.name if project else None,
        'subsystem_id': service.subsystem_id,
        'subsystem_name': subsystem.subsystem_name if subsystem else None,
        'group_id': service.group_id,
        'group_name': service_group.group_name if service_group else None,
        'func_desc': service.func_desc,
        'module': service.module,
        'ip': service.ip,
        'ssh_port': service.ssh_port,
        'username': service.username,
        'program_path': service.program_path,
        'start_script': service.start_script,
        'stop_script': service.stop_script,
        'log_path': service.log_path,
        'port': service.port,
        'owner': service.owner,
        'remark': service.remark,
        # 新增字段
        'service_type': service.service_type,
        'deploy_type': service.deploy_type,
        'container_name': service.container_name,
        'image_name': service.image_name,
        'image_tag': service.image_tag,
        'container_id': service.container_id,
        'port_mapping': service.port_mapping,
        'volume_mapping': service.volume_mapping,
        'network_mode': service.network_mode,
        'log_type': service.log_type,
        'agent_uuid': service.agent_uuid,
        'created_at': service.created_at,
        'updated_at': service.updated_at
    })

@router.delete("/services/{service_id}", response_model=ResponseModel)
async def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_manage"))
):
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    # DataScope：只能删除有权限项目下的服务
    assert_service_access(db, user, service_id, service=service)
    # 高风险：服务删除需项目共享独立授权
    assert_high_risk_capability(db, user, service.project_id, "delete")

    func_desc = service.func_desc
    agent_uuid = service.agent_uuid
    deleted_project_id = service.project_id
    deleted_subsystem_id = service.subsystem_id
    db.delete(service)
    db.commit()

    # 清除服务列表缓存
    from utils.cache import invalidate_services_list
    invalidate_services_list()

    # 通知关联的在线 Agent 刷新服务列表
    await notify_agents_pull_services(db, agent_uuid)

    log_audit(db, user.id, user.username, "SERVICE_DELETE",
              service_id=service_id,
              project_id=deleted_project_id,
              subsystem_id=deleted_subsystem_id,
              result="success", output=f"删除服务: {func_desc}")

    return ResponseModel(data={"id": service_id})

@router.put("/services/{service_id}/containers/run-mode", response_model=ResponseModel)
async def update_container_run_mode(
    service_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_manage"))
):
    """修改运行类型（常驻服务 permanent / 一次性任务 oneshot / 未启用 inactive）。

    按 (service_id, container_name) 唯一，container_name 传 "*" 表示服务级默认值
    （物理机服务无容器，只能用它；容器级配置优先于服务级默认）。
    默认无记录 = permanent，因此只有改成 oneshot/inactive 才需要落库；
    改回 permanent 时删除记录，保持"默认即常驻"的语义。
    """
    from models.service_container_config import ServiceContainerConfig
    import services.container_status_service as container_status_service

    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    # DataScope：只能修改有权限项目下的服务
    assert_service_access(db, user, service_id, service=service)
    # 项目写操作：只读共享不得修改运行模式
    assert_project_write_capability(db, user, service.project_id)

    container_name = (payload.get("container_name") or "").strip()
    run_mode = (payload.get("run_mode") or "").strip()
    if not container_name:
        raise HTTPException(status_code=400, detail="缺少 container_name")
    if run_mode not in (container_status_service.RUN_MODE_PERMANENT,
                        container_status_service.RUN_MODE_ONESHOT,
                        container_status_service.RUN_MODE_INACTIVE):
        raise HTTPException(status_code=400, detail="run_mode 必须为 permanent、oneshot 或 inactive")

    existing = (
        db.query(ServiceContainerConfig)
        .filter(
            ServiceContainerConfig.service_id == service_id,
            ServiceContainerConfig.container_name == container_name,
        )
        .first()
    )

    if run_mode == container_status_service.RUN_MODE_PERMANENT:
        # 默认值，无需保留记录
        if existing:
            db.delete(existing)
    elif existing:
        existing.run_mode = run_mode
        existing.updated_by = user.username
        existing.updated_at = datetime.now()
    else:
        db.add(ServiceContainerConfig(
            service_id=service_id,
            container_name=container_name,
            run_mode=run_mode,
            updated_by=user.username,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ))
    db.commit()

    log_audit(db, user.id, user.username, "SERVICE_UPDATE",
              service_id=service_id,
              result="success",
              output=f"修改容器运行类型: service={service_id} container={container_name} run_mode={run_mode}")

    return ResponseModel(data={"container_name": container_name, "run_mode": run_mode})

@router.post("/services/batch/delete", response_model=ResponseModel)
async def batch_delete_services(
    service_ids: List[int],
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_manage"))
):
    if not service_ids:
        raise HTTPException(status_code=400, detail="请选择要删除的服务")
    
    # 先收集要删除的服务关联的 agent_uuid（删除后就查不到了）
    # DataScope：逐个校验待删除服务的数据范围，任一越权则整批拒绝
    target_services = assert_services_access(db, user, service_ids)
    # 高风险：服务删除需项目共享独立授权（逐个校验项目）
    for _svc in target_services:
        assert_high_risk_capability(db, user, _svc.project_id, "delete")
    affected_agent_uuids = set(s.agent_uuid for s in target_services if s.agent_uuid)

    # 使用批量删除，提高性能
    deleted_count = db.query(AppService).filter(AppService.id.in_(service_ids)).delete(synchronize_session=False)
    
    if deleted_count > 0:
        db.commit()
        # 清除服务列表缓存
        from utils.cache import invalidate_services_list
        invalidate_services_list()
        log_audit(db, user.id, user.username, "SERVICE_DELETE",
                  result="success", output=f"批量删除服务 {deleted_count} 个")

        # 通知所有受影响的在线 Agent 刷新服务列表
        for agent_uuid in affected_agent_uuids:
            await notify_agents_pull_services(db, agent_uuid)
    
    return ResponseModel(data={"deleted": deleted_count})

@router.post("/services/status/batch", response_model=ResponseModel)
async def batch_get_status(
    service_ids: List[int],
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    from utils.redis_client import redis_client

    if not service_ids:
        return ResponseModel(data={})

    # DataScope：逐个校验数据范围，任一越权则整批拒绝
    services = assert_services_access(db, user, service_ids)

    # 【已禁用 SSH 状态检测】状态只能由 Agent 上报及心跳判断（Agent 离线 → UNKNOWN），
    # 原先经 get_batch_program_status 通过 SSH 探测服务状态属违规，现改为读取 Agent 写入的
    # Redis 缓存。响应结构与原接口保持一致（{service_id: 状态字符串}），缺失时返回 UNKNOWN。
    result = {}
    for service in services:
        status = redis_client.get(f"service_status:{service.id}")
        result[service.id] = status.decode('utf-8') if status else 'UNKNOWN'

    return ResponseModel(data=result)

@router.post("/services/status/cache", response_model=ResponseModel)
async def get_status_from_cache(
    service_ids: List[int],
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    from utils.redis_client import redis_client
    
    if not service_ids:
        return ResponseModel(data={})
    
    # DataScope：逐个校验数据范围，任一越权则整批拒绝
    assert_services_access(db, user, service_ids)
    
    result = {}
    try:
        for service_id in service_ids:
            redis_key = f"service_status:{service_id}"
            source_key = f"service_status_source:{service_id}"
            status = redis_client.get(redis_key)
            source = redis_client.get(source_key)
            print(f"[DEBUG] get_status_from_cache: service_id={service_id}, redis_key={redis_key}, status={status}, source_key={source_key}, source={source}")
            if status:
                result[service_id] = {
                    'status': status.decode('utf-8'),
                    # 来源缺失时不得伪标为 'SSH'，状态来源只能是 AGENT / OFFLINE
                    'source': source.decode('utf-8') if source else 'UNKNOWN'
                }
    except Exception as e:
        print(f"Redis cache error: {e}")
    
    return ResponseModel(data=result)

@router.post("/services/{service_id}/start", response_model=ResponseModel)
async def start_service(
    service_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_operate"))
):
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    # DataScope：只能操作有权限项目下的服务
    assert_service_access(db, user, service_id, service=service)
    # 项目写操作：只读共享不得启停/重启
    assert_project_write_capability(db, user, service.project_id)

    print(f"\n[START] Service {service_id}: func_desc={service.func_desc}, ip={service.ip}, agent_uuid={service.agent_uuid}, deploy_type={service.deploy_type}, program_path={service.program_path}, start_script={service.start_script}, username={service.username}")
    
    service_type = service.service_type or 'HOST_APP'
    result_message = ""
    output = ""
    success = False
    
    try:
        print(f"[START] Trying agent operation for service {service_id}...")
        agent_result = await try_agent_operation(service, "start")
        print(f"[START] Agent result for service {service_id}: {agent_result}")
        if agent_result is not None:
            success = agent_result.get('success', False)
            output = agent_result.get('output', '')
            result_message = agent_result.get('message', 'Agent操作完成')
            log_audit(db, user.id, user.username, "SERVICE_START",
                      service_id=service.id,
                      project_id=service.project_id,
                      subsystem_id=service.subsystem_id,
                      result="success" if success else "failed",
                      output=f"服务: {service.func_desc}, IP: {service.ip}, 通过Agent启动, 结果: {result_message}")
            return ResponseModel(data={"success": success, "message": result_message, "output": output})
        
        ssh = await ssh_pool.get_connection(service.ip, service.ssh_port or 22, service.username, decrypt(service.password))
        if not ssh:
            return ResponseModel(data={"success": False, "message": "无法建立SSH连接"}, code=500)
        
        # 根据服务类型执行不同的启动命令
        if service_type == 'DOCKER':
            # Docker容器部署 - 使用容器名称启动
            if service.container_name:
                command = f"docker start {service.container_name}"
                output, error, cmd_success = await ssh.execute_command(command)
                if cmd_success:
                    result_message = "Docker容器启动成功"
                    success = True
                else:
                    result_message = f"启动失败: {error}"
            else:
                result_message = "未配置容器名称"
        
        elif service_type == 'DOCKER_COMPOSE':
            # Docker Compose部署 - 使用docker-compose up -d
            if service.program_path:
                command = f"cd {expand_home_path(service.program_path)} && docker-compose up -d"
                output, error, cmd_success = await ssh.execute_command(command)
                if cmd_success:
                    result_message = "Docker Compose 服务启动成功"
                    success = True
                else:
                    result_message = f"启动失败: {error}"
            else:
                result_message = "未配置程序路径"
        
        elif service_type in ['ES', 'SOLR']:
            # ES/SOLR服务 - 节点启动
            if service.start_script:
                command = f"cd {expand_home_path(service.program_path)} && {format_script_command(service.start_script)}"
                output, error, cmd_success = await ssh.execute_command(command)
                if cmd_success:
                    result_message = "服务启动命令已执行"
                    success = True
                else:
                    result_message = f"启动失败: {error}"
            else:
                result_message = "未配置启动脚本"
        
        else:
            # HOST_APP及其他服务类型
            if not service.start_script:
                return ResponseModel(data={"success": False, "message": "未配置启动脚本"}, code=400)
            
            command = f"cd {expand_home_path(service.program_path)} && {format_script_command(service.start_script)}"
            output, error, cmd_success = await ssh.execute_command(command)
            
            await asyncio.sleep(2)
            
            status = await get_program_status(service.ip, service.username, decrypt(service.password), service.port, service.program_path, service.ssh_port or 22)
            
            success = status == "RUNNING"
            result_message = "启动成功" if success else "启动命令已执行，请检查状态"
        
        ssh.close()
        
        log_audit(db, user.id, user.username, "SERVICE_START",
                  service_id=service.id,
                  project_id=service.project_id,
                  subsystem_id=service.subsystem_id,
                  result="success" if success else "partial",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 类型: {service_type}, 命令: {command}, 输出: {output[:200]}")
        
        return ResponseModel(data={"success": success, "message": result_message, "output": output[:500]})
    except Exception as e:
        log_audit(db, user.id, user.username, "SERVICE_START",
                  service_id=service.id,
                  project_id=service.project_id,
                  subsystem_id=service.subsystem_id,
                  result="failed",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 类型: {service_type}, 错误: {str(e)}")
        return ResponseModel(data={"success": False, "message": str(e), "output": None}, code=500)

@router.post("/services/{service_id}/stop", response_model=ResponseModel)
async def stop_service(
    service_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_operate"))
):
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    # DataScope：只能操作有权限项目下的服务
    assert_service_access(db, user, service_id, service=service)
    # 项目写操作：只读共享不得启停/重启
    assert_project_write_capability(db, user, service.project_id)

    service_type = service.service_type or 'HOST_APP'
    result_message = ""
    output = ""
    success = False
    
    try:
        agent_result = await try_agent_operation(service, "stop")
        if agent_result is not None:
            success = agent_result.get('success', False)
            output = agent_result.get('output', '')
            result_message = agent_result.get('message', 'Agent操作完成')
            log_audit(db, user.id, user.username, "SERVICE_STOP",
                      service_id=service.id,
                      project_id=service.project_id,
                      subsystem_id=service.subsystem_id,
                      result="success" if success else "failed",
                      output=f"服务: {service.func_desc}, IP: {service.ip}, 通过Agent停止, 结果: {result_message}")
            return ResponseModel(data={"success": success, "message": result_message, "output": output})
        
        ssh = await ssh_pool.get_connection(service.ip, service.ssh_port or 22, service.username, decrypt(service.password))
        if not ssh:
            return ResponseModel(data={"success": False, "message": "无法建立SSH连接"}, code=500)
        
        # 根据服务类型执行不同的停止命令
        if service_type == 'DOCKER':
            # Docker容器部署 - 使用容器名称停止
            if service.container_name:
                command = f"docker stop {service.container_name}"
                output, error, cmd_success = await ssh.execute_command(command)
                if cmd_success:
                    result_message = "Docker容器停止成功"
                    success = True
                else:
                    result_message = f"停止失败: {error}"
            else:
                result_message = "未配置容器名称"
        
        elif service_type == 'DOCKER_COMPOSE':
            # Docker Compose部署 - 使用docker-compose down
            if service.program_path:
                command = f"cd {expand_home_path(service.program_path)} && docker-compose down"
                output, error, cmd_success = await ssh.execute_command(command)
                if cmd_success:
                    result_message = "Docker Compose 服务停止成功"
                    success = True
                else:
                    result_message = f"停止失败: {error}"
            else:
                result_message = "未配置程序路径"
        
        elif service_type in ['ES', 'SOLR']:
            # ES/SOLR服务 - 禁止直接停止整个生产集群
            if service.deploy_type == 'CLUSTER':
                ssh.close()
                return ResponseModel(data={"success": False, "message": "禁止直接停止集群，请先确认是否要停止单个节点"}, code=400)
            
            # 单个节点停止
            if service.stop_script:
                command = f"cd {expand_home_path(service.program_path)} && {format_script_command(service.stop_script)}"
                output, error, cmd_success = await ssh.execute_command(command)
                if cmd_success:
                    result_message = "节点停止命令已执行"
                    success = True
                else:
                    result_message = f"停止失败: {error}"
            else:
                result_message = "未配置停止脚本"
        
        else:
            # HOST_APP及其他服务类型
            if not service.stop_script:
                return ResponseModel(data={"success": False, "message": "未配置停止脚本"}, code=400)
            
            command = f"cd {expand_home_path(service.program_path)} && {format_script_command(service.stop_script)}"
            output, error, cmd_success = await ssh.execute_command(command)
            
            await asyncio.sleep(2)
            
            status = await get_program_status(service.ip, service.username, decrypt(service.password), service.port, service.program_path, service.ssh_port or 22)
            
            success = status == "STOPPED"
            result_message = "停止成功" if success else "停止命令已执行，请检查状态"
        
        ssh.close()
        
        log_audit(db, user.id, user.username, "SERVICE_STOP",
                  service_id=service.id,
                  project_id=service.project_id,
                  subsystem_id=service.subsystem_id,
                  result="success" if success else "partial",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 类型: {service_type}, 命令: {command}, 输出: {output[:200]}")
        
        return ResponseModel(data={"success": success, "message": result_message, "output": output[:500]})
    except Exception as e:
        log_audit(db, user.id, user.username, "SERVICE_STOP",
                  service_id=service.id,
                  project_id=service.project_id,
                  subsystem_id=service.subsystem_id,
                  result="failed",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 类型: {service_type}, 错误: {str(e)}")
        return ResponseModel(data={"success": False, "message": str(e), "output": None}, code=500)

@router.post("/services/{service_id}/restart", response_model=ResponseModel)
async def restart_service(
    service_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_operate"))
):
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    # DataScope：只能操作有权限项目下的服务
    assert_service_access(db, user, service_id, service=service)
    # 项目写操作：只读共享不得启停/重启
    assert_project_write_capability(db, user, service.project_id)

    service_type = service.service_type or 'HOST_APP'
    result_message = ""
    output = ""
    success = False
    
    try:
        agent_result = await try_agent_operation(service, "restart")
        if agent_result is not None:
            success = agent_result.get('success', False)
            output = agent_result.get('output', '')
            result_message = agent_result.get('message', 'Agent操作完成')
            log_audit(db, user.id, user.username, "SERVICE_RESTART",
                      service_id=service.id,
                      project_id=service.project_id,
                      subsystem_id=service.subsystem_id,
                      result="success" if success else "failed",
                      output=f"服务: {service.func_desc}, IP: {service.ip}, 通过Agent重启, 结果: {result_message}")
            return ResponseModel(data={"success": success, "message": result_message, "output": output})
        
        ssh = await ssh_pool.get_connection(service.ip, service.ssh_port or 22, service.username, decrypt(service.password))
        if not ssh:
            return ResponseModel(data={"success": False, "message": "无法建立SSH连接"}, code=500)
        
        # 根据服务类型执行不同的重启命令
        if service_type == 'DOCKER' and service.container_name:
            # Docker服务
            command = f"docker restart {service.container_name}"
            output, error, cmd_success = await ssh.execute_command(command)
            if cmd_success:
                result_message = "Docker容器重启成功"
                success = True
            else:
                result_message = f"重启失败: {error}"
        
        elif service_type in ['ES', 'SOLR']:
            # ES/SOLR服务 - 禁止直接重启整个生产集群
            if service.deploy_type == 'CLUSTER':
                ssh.close()
                return ResponseModel(data={"success": False, "message": "禁止直接重启集群，请先确认是否要重启单个节点"}, code=400)
            
            # 单个节点重启
            if service.stop_script:
                stop_command = f"cd {expand_home_path(service.program_path)} && {format_script_command(service.stop_script)}"
                await ssh.execute_command(stop_command)
                await asyncio.sleep(1)
            
            if service.start_script:
                start_command = f"cd {expand_home_path(service.program_path)} && {format_script_command(service.start_script)}"
                output, error, cmd_success = await ssh.execute_command(start_command)
                if cmd_success:
                    result_message = "节点重启命令已执行"
                    success = True
                else:
                    result_message = f"重启失败: {error}"
            else:
                result_message = "未配置启动脚本"
        
        else:
            # HOST_APP及其他服务类型
            if service.stop_script:
                command = f"cd {expand_home_path(service.program_path)} && {format_script_command(service.stop_script)}"
                await ssh.execute_command(command)
                await asyncio.sleep(1)
            
            if service.start_script:
                command = f"cd {expand_home_path(service.program_path)} && {format_script_command(service.start_script)}"
                output, error, cmd_success = await ssh.execute_command(command)
            else:
                output = "未配置启动脚本"
            
            await asyncio.sleep(2)
            
            status = await get_program_status(service.ip, service.username, decrypt(service.password), service.port, service.program_path, service.ssh_port or 22)
            
            success = status == "RUNNING"
            result_message = "重启成功" if success else "重启命令已执行，请检查状态"
        
        ssh.close()
        
        log_audit(db, user.id, user.username, "SERVICE_RESTART",
                  service_id=service.id,
                  project_id=service.project_id,
                  subsystem_id=service.subsystem_id,
                  result="success" if success else "partial",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 类型: {service_type}, 输出: {output[:200]}")
        
        return ResponseModel(data={"success": success, "message": result_message, "output": output[:500]})
    except Exception as e:
        log_audit(db, user.id, user.username, "SERVICE_RESTART",
                  service_id=service.id,
                  project_id=service.project_id,
                  subsystem_id=service.subsystem_id,
                  result="failed",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 类型: {service_type}, 错误: {str(e)}")
        return ResponseModel(data={"success": False, "message": str(e), "output": None}, code=500)

@router.get("/services/{service_id}/log/files", response_model=ResponseModel)
async def list_log_files(
    service_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    # DataScope：只能查看有权限项目下服务的日志
    assert_service_access(db, user, service_id, service=service)

    try:
        ssh = await ssh_pool.get_connection(service.ip, service.ssh_port or 22, service.username, decrypt(service.password))
        if not ssh:
            return ResponseModel(data={"files": [], "message": "无法建立SSH连接"}, code=500)
        
        # Docker部署处理
        if service.deploy_type == 'DOCKER':
            # 如果是Docker Logs方式，返回容器名称作为日志标识
            if service.log_type == 'DOCKER_LOGS':
                ssh.close()
                return ResponseModel(data={
                    "files": [{"name": "docker.log", "size": "实时", "date": "实时"}],
                    "log_dir": "docker_logs",
                    "log_type": "DOCKER_LOGS",
                    "container_name": service.container_name
                })
            
            # 主机目录方式
            if not service.log_path:
                ssh.close()
                return ResponseModel(data={"files": [], "message": "未配置日志路径"}, code=400)
            
            program_dir = expand_home_path(service.program_path)
            log_dir = service.log_path
            
            command = f"cd {program_dir}/{log_dir} && ls -lht *.log 2>/dev/null | awk '{{print $9, $5, $6, $7, $8}}'"
            output, error, success = await ssh.execute_command(command)
            ssh.close()
            
            if success and output.strip():
                files = []
                for line in output.strip().split('\n'):
                    if line.strip():
                        parts = line.split(None, 4)
                        if len(parts) >= 5:
                            files.append({
                                "name": parts[0],
                                "size": parts[1],
                                "date": " ".join(parts[2:5])
                            })
                
                return ResponseModel(data={"files": files, "log_dir": log_dir, "log_type": "HOST_DIR"})
            else:
                return ResponseModel(data={"files": [{"name": service.log_path, "size": "unknown", "date": "unknown"}], "log_dir": service.log_path, "log_type": "HOST_DIR"})
        
        # 主机部署处理（原有逻辑）
        else:
            if not service.log_path:
                ssh.close()
                return ResponseModel(data={"files": [], "message": "未配置日志路径"}, code=400)
            
            program_dir = expand_home_path(service.program_path)
            log_dir = service.log_path
            
            command = f"cd {program_dir}/{log_dir} && ls -lht *.log 2>/dev/null | awk '{{print $9, $5, $6, $7, $8}}'"
            output, error, success = await ssh.execute_command(command)
            ssh.close()
            
            if success and output.strip():
                files = []
                for line in output.strip().split('\n'):
                    if line.strip():
                        parts = line.split(None, 4)
                        if len(parts) >= 5:
                            files.append({
                                "name": parts[0],
                                "size": parts[1],
                                "date": " ".join(parts[2:5])
                            })
                
                return ResponseModel(data={"files": files, "log_dir": log_dir})
            else:
                return ResponseModel(data={"files": [{"name": service.log_path, "size": "unknown", "date": "unknown"}], "log_dir": service.log_path})
    except Exception as e:
        return ResponseModel(data={"files": [], "message": f"获取日志文件列表失败: {str(e)}"}, code=500)

@router.websocket("/services/{service_id}/log/ws")
async def service_log_websocket(websocket: WebSocket, service_id: int, token: str = Query(None), db: Session = Depends(get_db)):
    await websocket.accept()
    
    # 1. token 校验 + 用户身份
    from services.auth_service import decode_access_token
    from models.user import User
    from api.permission_dependencies import user_can_access_project
    payload = decode_access_token(token) if token else None
    username = payload.get("sub") if payload else None
    if not username:
        await websocket.send_json({"type": "error", "message": "无效的认证token"})
        await websocket.close(code=1008)
        return
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        await websocket.send_json({"type": "error", "message": "用户无效或已被禁用"})
        await websocket.close(code=1008)
        return
    
    # 2. 服务存在性校验
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        await websocket.send_json({"type": "error", "message": "服务不存在"})
        await websocket.close(code=1008)
        return
    
    # 3. 数据范围校验：只能订阅有权限项目下服务的日志
    if not user_can_access_project(db, user, service.project_id):
        await websocket.send_json({"type": "error", "message": "无权访问该服务"})
        await websocket.close(code=1008)
        return
    
    from api.agent import manager
    
    if service.agent_uuid and manager.is_online(service.agent_uuid):
        try:
            manager.subscribe_log(str(service_id), websocket)
            
            request_id = str(uuid.uuid4())
            message = {
                "type": "command",
                "request_id": request_id,
                "timestamp": datetime.now().timestamp(),
                "data": {
                    "service_id": str(service.id),
                    "action": "logs",
                    "deploy_type": service.deploy_type,
                    "docker_name": service.container_name,
                    "compose_path": service.program_path,
                    "log_path": service.log_path,
                    "start_cmd": service.start_script,
                    "stop_cmd": service.stop_script,
                    "restart_cmd": service.restart_script,
                }
            }
            
            await manager.send_message(service.agent_uuid, message)
            
            while True:
                try:
                    await websocket.receive_text()
                except WebSocketDisconnect:
                    break
        except Exception as e:
            await websocket.send_json({"type": "error", "message": f"Agent日志推送失败: {str(e)}"})
            await websocket.close()
        finally:
            manager.unsubscribe_log(str(service_id), websocket)
    else:
        await websocket.send_json({"type": "error", "message": "Agent未在线，无法实时推送日志"})
        await websocket.close()

@router.get("/services/{service_id}/log", response_model=ResponseModel)
async def get_service_log(
    service_id: int,
    lines: int = Query(200, ge=10, le=5000),
    filename: str = Query(None, description="日志文件名"),
    keyword: str = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    # DataScope：只能查看有权限项目下服务的日志
    assert_service_access(db, user, service_id, service=service)

    try:
        ssh = await ssh_pool.get_connection(service.ip, service.ssh_port or 22, service.username, decrypt(service.password))
        if not ssh:
            return ResponseModel(data={"content": "无法建立SSH连接"}, code=500)
        
        # Docker部署处理
        if service.deploy_type == 'DOCKER':
            container_name = service.container_name
            
            # 如果有日志路径配置，说明是挂载的主机目录日志
            if service.log_path and service.log_type == 'HOST_DIR':
                program_dir = expand_home_path(service.program_path)
                log_dir = service.log_path
                
                if filename:
                    log_file = f"{program_dir}/{log_dir}/{filename}"
                else:
                    command = f"cd {program_dir}/{log_dir} && ls -t *.log 2>/dev/null | head -1"
                    output, error, success = await ssh.execute_command(command)
                    log_file = output.strip()
                    if not log_file:
                        ssh.close()
                        return ResponseModel(data={"content": "日志目录下未找到日志文件"})
                    log_file = f"{program_dir}/{log_dir}/{log_file}"
                
                if keyword:
                    command = f"grep -n '{keyword}' {log_file} | tail -n {lines}"
                else:
                    command = f"tail -n {lines} {log_file}"
                
                content, error_output, success = await ssh.execute_command(command)
                ssh.close()
                
                if error_output and not keyword:
                    content = f"警告: {error_output}\n\n{content}"
                
                return ResponseModel(data={"content": content, "filename": filename or "latest.log"})
            
            # Docker Logs方式
            else:
                if not container_name:
                    ssh.close()
                    return ResponseModel(data={"content": "未配置容器名称，无法查看Docker日志"}, code=400)
                
                if keyword:
                    command = f"docker logs {container_name} 2>&1 | grep -n '{keyword}' | tail -n {lines}"
                else:
                    command = f"docker logs --tail {lines} {container_name} 2>&1"
                
                content, error_output, success = await ssh.execute_command(command)
                ssh.close()
                
                if error_output and not success:
                    content = f"错误: {error_output}"
                
                return ResponseModel(data={"content": content, "filename": "docker.log"})
        
        # 主机部署处理（原有逻辑）
        else:
            if not service.log_path:
                ssh.close()
                return ResponseModel(data={"content": "未配置日志路径"}, code=400)
            
            program_dir = expand_home_path(service.program_path)
            log_dir = service.log_path
            
            if filename:
                log_file = f"{program_dir}/{log_dir}/{filename}"
            else:
                command = f"cd {program_dir}/{log_dir} && ls -t *.log 2>/dev/null | head -1"
                output, error, success = await ssh.execute_command(command)
                log_file = output.strip()
                if not log_file:
                    ssh.close()
                    return ResponseModel(data={"content": "日志目录下未找到日志文件"})
                log_file = f"{program_dir}/{log_dir}/{log_file}"
            
            if keyword:
                command = f"grep -n '{keyword}' {log_file} | tail -n {lines}"
            else:
                command = f"tail -n {lines} {log_file}"
            
            content, error_output, success = await ssh.execute_command(command)
            ssh.close()
            
            if error_output and not keyword:
                content = f"警告: {error_output}\n\n{content}"
            
            return ResponseModel(data={"content": content, "filename": filename or "latest.log"})
    except Exception as e:
        return ResponseModel(data={"content": f"读取日志失败: {str(e)}"}, code=500)

@router.get("/services/{service_id}/log/download")
async def download_service_log(
    service_id: int,
    filename: str = Query(None, description="日志文件名"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    # DataScope：只能下载有权限项目下服务的日志
    assert_service_access(db, user, service_id, service=service)

    if not service.log_path:
        raise HTTPException(status_code=400, detail="未配置日志路径")
    
    try:
        ssh = await ssh_pool.get_connection(service.ip, service.ssh_port or 22, service.username, decrypt(service.password))
        if not ssh:
            raise HTTPException(status_code=500, detail="无法建立SSH连接")
        
        program_dir = expand_home_path(service.program_path)
        log_dir = service.log_path
        
        if filename:
            log_file = filename
        else:
            command = f"cd {program_dir}/{log_dir} && ls -t *.log 2>/dev/null | head -1"
            output, error, success = await ssh.execute_command(command)
            log_file = output.strip()
            if not log_file:
                ssh.close()
                raise HTTPException(status_code=400, detail="日志目录下未找到日志文件")
        
        command = f"cat {program_dir}/{log_dir}/{log_file}"
        output, error, success = await ssh.execute_command(command)
        
        ssh.close()
        
        filename = f"{service.func_desc}_{log_file}"
        encoded_filename = quote(filename, safe='')
        return StreamingResponse(
            io.BytesIO(output.encode('utf-8')),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载日志失败: {str(e)}")

@router.post("/services/import", response_model=ResponseModel)
async def import_services(
    file: UploadFile = File(...),
    project_id: Optional[int] = Form(None),
    subsystem_id: Optional[int] = Form(None),
    group_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_manage"))
):
    from models.service_group import ServiceGroup
    from models.subsystem import Subsystem
    from models.subsystem_group_relation import SubsystemGroupRelation
    
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="仅支持xlsx格式文件")
    
    # 中文标题到字段名的映射
    header_mapping = {
        '功能描述': 'func_desc',
        '对应模块': 'module',
        'IP': 'ip',
        'IP地址': 'ip',
        '用户名': 'username',
        '密码': 'password',
        '程序路径': 'program_path',
        '启动方式': 'start_script',
        '启动方式（必须要有脚本）': 'start_script',
        '停止方式': 'stop_script',
        '停止方式（必须要有脚本）': 'stop_script',
        '日志路径': 'log_path',
        '程序本身启用的端口': 'port',
        '端口': 'port',
        '负责人': 'owner',
        '责任人': 'owner',
        '备注': 'remark',
        # Docker相关字段
        '容器名称': 'container_name',
        '容器名': 'container_name',
        '镜像名称': 'image_name',
        '镜像名': 'image_name',
        '镜像版本': 'image_tag',
        '镜像标签': 'image_tag',
        '容器ID': 'container_id',
        '端口映射': 'port_mapping',
        'Volume挂载': 'volume_mapping',
        '网络模式': 'network_mode',
        # 兼容旧模板标题
        '项目名称': 'project_name',
        '服务名称': 'func_desc',
        '模块': 'module',
        # 兼容英文标题
        'func_desc': 'func_desc',
        'module': 'module',
        'ip': 'ip',
        'username': 'username',
        'password': 'password',
        'program_path': 'program_path',
        'start_script': 'start_script',
        'stop_script': 'stop_script',
        'log_path': 'log_path',
        'port': 'port',
        'owner': 'owner',
        'remark': 'remark',
        # 英文Docker字段
        'container_name': 'container_name',
        'image_name': 'image_name',
        'image_tag': 'image_tag',
        'container_id': 'container_id',
        'port_mapping': 'port_mapping',
        'volume_mapping': 'volume_mapping',
        'network_mode': 'network_mode'
    }
    
    # 模糊匹配函数 - 根据表头中的关键字段匹配
    def fuzzy_match_header(header):
        """根据表头中的关键字进行模糊匹配"""
        if not header:
            return None
        header_str = str(header).strip()
        # 先尝试精确匹配
        if header_str in header_mapping:
            return header_mapping[header_str]
        # 模糊匹配 - 按关键字判断
        for keyword, field in [
            ('功能', 'func_desc'),
            ('描述', 'func_desc'),
            ('模块', 'module'),
            ('IP', 'ip'),
            ('地址', 'ip'),
            ('用户', 'username'),
            ('密码', 'password'),
            ('程序路径', 'program_path'),
            ('路径', 'program_path'),
            ('启动', 'start_script'),
            ('停止', 'stop_script'),
            ('日志', 'log_path'),
            ('端口', 'port'),
            ('部署方式', 'deploy_type'),
            ('负责', 'owner'),
            ('责任', 'owner'),
            ('备注', 'remark'),
            # Docker相关字段模糊匹配
            ('容器', 'container_name'),
            ('镜像', 'image_name'),
            ('端口映射', 'port_mapping'),
            ('映射', 'port_mapping'),
        ]:
            if keyword in header_str:
                return field
        return None
    
    # 自动判断部署方式和服务类型
    def detect_deploy_and_service_type(row_data):
        """根据导入数据自动判断部署方式和服务类型"""
        deploy_type_raw = row_data.get('deploy_type', '').strip() if row_data.get('deploy_type') else ''
        if deploy_type_raw:
            if 'compose' in deploy_type_raw.lower():
                return 'DOCKER_COMPOSE', 'DOCKER_COMPOSE'
            elif 'docker' in deploy_type_raw.lower() or '容器' in deploy_type_raw:
                return 'DOCKER', 'DOCKER'
            elif 'host' in deploy_type_raw.lower() or '主机' in deploy_type_raw:
                return 'HOST', 'HOST_APP'
        
        docker_indicators = [
            row_data.get('container_name'),
            row_data.get('image_name'),
            row_data.get('container_id'),
            row_data.get('port_mapping'),
        ]
        
        has_docker_data = any(indicator for indicator in docker_indicators if indicator and str(indicator).strip())
        
        if has_docker_data:
            return 'DOCKER', 'DOCKER'
        else:
            return 'HOST', 'HOST_APP'
    
    try:
        file_content = await file.read()
        wb = load_workbook(filename=io.BytesIO(file_content), read_only=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")
    
    # 获取所有程序分类，用于匹配 sheet 名称
    all_groups = db.query(ServiceGroup).all()
    group_name_to_id = {group.group_name: group.id for group in all_groups}
    
    # 导入用于生成唯一 code 的库
    import hashlib
    
    # 如果没有选择子系统，获取或创建默认子系统
    default_subsystem_created = False
    if not subsystem_id:
        # 先确定使用哪个项目
        project = None
        if project_id:
            project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            project = db.query(Project).first()

        if project:
            # 查找项目的默认子系统（名称为"默认子系统"）
            default_subsystem = db.query(Subsystem).filter(
                Subsystem.project_id == project.id,
                Subsystem.subsystem_name == '默认子系统'
            ).first()
            if not default_subsystem:
                # 创建默认子系统，subsystem_code 现在是项目内唯一，不再需要按项目区分
                default_subsystem = Subsystem(
                    project_id=project.id,
                    subsystem_name='默认子系统',
                    subsystem_code='DEFAULT_SUBSYSTEM',
                    description='导入Excel自动创建的默认子系统'
                )
                db.add(default_subsystem)
                db.flush()
                db.commit()
                default_subsystem_created = True
                print(f"Created default subsystem: {default_subsystem.id}")
            # 使用默认子系统
            subsystem_id = default_subsystem.id

    # 打印调试信息
    print(f"Available groups: {list(group_name_to_id.keys())}")
    print(f"Sheet names: {wb.sheetnames}")
    print(f"Using subsystem_id: {subsystem_id}")

    added = 0
    updated = 0
    repaired = 0
    skipped = 0
    failed = 0
    failed_items = []

    # ---------------- 导入批次记录（支持撤销） ----------------
    from models.import_batch import ImportBatch, ImportBatchOperation

    # 确定批次归属项目（与后续建服务使用的项目解析规则一致）
    batch_project = None
    if project_id:
        batch_project = db.query(Project).filter(Project.id == project_id).first()
    if not batch_project:
        batch_project = db.query(Project).first()

    # DataScope：只能向有权限的项目导入服务
    assert_project_access(db, user, batch_project.id if batch_project else None,
                          detail="无权向该项目导入服务")
    # 项目级高风险独立授权：导入即批量创建/部署服务，仅共享访问的用户需被授予 deploy 高风险能力
    assert_high_risk_capability(db, user, batch_project.id if batch_project else None, "deploy",
                                detail="该项目共享未授予服务部署权限")

    # 导入前自动快照（兜底保险），失败不阻塞导入
    pre_snapshot_id = None
    try:
        from services.backup_service import run_backup as _run_backup
        snap_rec = _run_backup(backup_type='pre_import', created_by=user.username)
        if snap_rec.status == 'success':
            pre_snapshot_id = snap_rec.id
    except Exception as _snap_err:
        print(f"[import] pre-import snapshot skipped: {_snap_err}")

    batch = ImportBatch(
        batch_no=str(_uuid.uuid4()),
        filename=file.filename,
        project_id=batch_project.id if batch_project else (project_id or 0),
        project_name=batch_project.name if batch_project else None,
        subsystem_id=subsystem_id,
        group_id=group_id,
        pre_backup_record_id=pre_snapshot_id,
        default_subsystem_created=1 if default_subsystem_created else 0,
        created_by=user.username,
        created_at=datetime.now(),
    )
    db.add(batch)
    db.commit()

    created_ids = []            # 本次新增的服务ID列表
    repaired_ops = []           # 本次补全归属的旧值快照
    auto_created_group_ids = []  # 本次导入新建的分类ID

    # 遍历所有 sheet
    for sheet_idx, sheet_name in enumerate(wb.sheetnames):
        ws = wb[sheet_name]
        
        # 根据 sheet 名称匹配分类（仅精确匹配+忽略大小写匹配）
        matched_group_id = None
        sheet_name_clean = sheet_name.strip()
        sheet_name_lower = sheet_name_clean.lower()
        
        # 1. 精确匹配
        if sheet_name_clean in group_name_to_id:
            matched_group_id = group_name_to_id[sheet_name_clean]
        else:
            # 2. 忽略大小写匹配
            for group_name, group_id in group_name_to_id.items():
                if group_name.lower() == sheet_name_lower:
                    matched_group_id = group_id
                    break
        
        if matched_group_id:
            # 使用匹配到的分类
            current_group_id = matched_group_id
            matched_group_name = list(group_name_to_id.keys())[list(group_name_to_id.values()).index(matched_group_id)]
            print(f"Sheet '{sheet_name}' matched to group '{matched_group_name}' (ID: {matched_group_id})")
        else:
            # 没有匹配到分类，先检查数据库中是否已存在同名分类（可能是之前导入创建的）
            existing_by_name = db.query(ServiceGroup).filter(ServiceGroup.group_name == sheet_name_clean).first()
            if existing_by_name:
                # 已存在同名分类，直接使用
                current_group_id = existing_by_name.id
                group_name_to_id[sheet_name_clean] = current_group_id
                print(f"Sheet '{sheet_name}' found existing group '{sheet_name_clean}' (ID: {current_group_id})")
            else:
                # 创建新分类
                code_hash = hashlib.md5(sheet_name.encode('utf-8')).hexdigest()[:8].upper()
                new_group_code = f"AUTO_{code_hash}"
                
                new_group = ServiceGroup(
                    group_name=sheet_name_clean,
                    group_code=new_group_code,
                    display_order=sheet_idx,
                    description=f"导入Excel自动创建的分类"
                )
                db.add(new_group)
                db.flush()
                db.commit()
                
                current_group_id = new_group.id
                group_name_to_id[sheet_name_clean] = current_group_id
                auto_created_group_ids.append(current_group_id)
                print(f"Sheet '{sheet_name}' auto-created group '{sheet_name_clean}' (ID: {current_group_id}, code: {new_group_code}, order: {sheet_idx})")
        
        # 将分类关联到子系统（无论是否新创建的）
        if subsystem_id and current_group_id:
            existing_relation = db.query(SubsystemGroupRelation).filter(
                SubsystemGroupRelation.subsystem_id == subsystem_id,
                SubsystemGroupRelation.group_id == current_group_id
            ).first()
            if not existing_relation:
                new_relation = SubsystemGroupRelation(
                    subsystem_id=subsystem_id,
                    group_id=current_group_id,
                    display_order=sheet_idx
                )
                db.add(new_relation)
                db.commit()
                print(f"Linked group '{sheet_name_clean}' (ID: {current_group_id}) to subsystem (ID: {subsystem_id}, order: {sheet_idx})")
            elif existing_relation.display_order != sheet_idx:
                # 已存在但顺序不对，更新为当前导入的 sheet 顺序
                existing_relation.display_order = sheet_idx
                db.commit()
                print(f"Updated relation order to {sheet_idx} for group '{sheet_name_clean}' (ID: {current_group_id})")
        
        # 读取当前 sheet 的表头
        headers = []
        for col in range(1, ws.max_column + 1):
            header = ws.cell(row=1, column=col).value
            headers.append(header.strip() if header else '')
        
        # 读取当前 sheet 的数据行
        rows = []
        for row in range(2, ws.max_row + 1):
            row_data = {}
            for col in range(1, ws.max_column + 1):
                header = headers[col - 1]
                value = ws.cell(row=row, column=col).value
                if value is not None:
                    # 使用模糊匹配将表头映射到字段名
                    field_name = fuzzy_match_header(header)
                    if field_name:
                        row_data[field_name] = str(value) if isinstance(value, (int, float)) else value
            if row_data:
                rows.append(row_data)
        
        # 处理当前 sheet 的数据
        for idx, row in enumerate(rows):
            try:
                func_desc = str(row.get('func_desc', '')).strip()
                module = str(row.get('module', '')).strip()
                ip = str(row.get('ip', '')).strip()
                program_path = str(row.get('program_path', '')).strip()
                port_raw = str(row.get('port', '')).strip()
                remark = str(row.get('remark', '')).strip()
                owner = str(row.get('owner', '')).strip()
                
                # 判断是否为备注行（智能识别）
                # 1. 没有任何关键字段（描述、IP、模块、程序路径）
                # 2. 或者描述以备注前缀开头（如 PS:、备注：、注：、说明：、注意：等）
                remark_prefixes = ['PS:', 'PS：', '备注:', '备注：', '注:', '说明:', '注意:', '说明：', '注意：']
                is_remark_line = False
                
                has_key_fields = any([ip, module, program_path])
                
                # 如果 func_desc 以备注前缀开头，且没有其他关键字段，则视为备注行
                if func_desc and not has_key_fields:
                    desc_lower = func_desc.lower()
                    for prefix in remark_prefixes:
                        if desc_lower.startswith(prefix.lower()):
                            is_remark_line = True
                            break
                
                # 如果没有任何关键字段，或识别为备注行，则跳过
                if not has_key_fields and not func_desc:
                    skipped += 1
                    continue
                elif is_remark_line:
                    skipped += 1
                    continue
                
                # 自动判断部署方式和服务类型
                deploy_type, service_type = detect_deploy_and_service_type(row)
                
                # 收集缺失的必填字段
                missing_fields = []
                if not func_desc:
                    missing_fields.append('功能描述')
                if not ip:
                    missing_fields.append('IP地址')
                # 根据部署方式判断是否需要程序路径
                if deploy_type in ['HOST', 'DOCKER', 'DOCKER_COMPOSE'] and not program_path:
                    missing_fields.append('程序路径')
                
                if missing_fields:
                    failed += 1
                    failed_items.append({
                        "row": idx + 2, 
                        "sheet": sheet_name, 
                        "reason": f"缺少必填字段",
                        "missing_fields": missing_fields,
                        "row_data": row
                    })
                    continue
                
                # 清理端口数据：支持多个端口，用逗号、分号或空格分隔
                port_value = None
                if port_raw:
                    # 清理端口字符串，支持逗号、分号、空格作为分隔符
                    port_parts = []
                    # 先将分号和空格替换为逗号，然后按逗号分割
                    normalized_ports = port_raw.replace('，', ',').replace(';', ',').replace('；', ',').replace('\\', ',')
                    # 处理空格分隔：先按逗号分割，再对每个部分按空格分割
                    comma_parts = normalized_ports.split(',')
                    for comma_part in comma_parts:
                        # 对每个逗号分割的部分，再按空白字符分割
                        space_parts = comma_part.split()
                        for p in space_parts:
                            p = p.strip()
                            if p:
                                try:
                                    port_num = int(p)
                                    if 1 <= port_num <= 65535:
                                        port_parts.append(str(port_num))
                                    else:
                                        failed += 1
                                        failed_items.append({
                                            "row": idx + 2, 
                                            "sheet": sheet_name, 
                                            "reason": f"端口号 {p} 不在有效范围(1-65535)",
                                            "row_data": row
                                        })
                                        continue
                                except ValueError:
                                    failed += 1
                                    failed_items.append({
                                        "row": idx + 2, 
                                        "sheet": sheet_name, 
                                        "reason": f"端口 '{p}' 不是有效的数字",
                                        "row_data": row
                                    })
                                    continue
                    if port_parts:
                        port_value = ','.join(port_parts)
                
                # 通过功能描述、对应模块、IP地址、程序路径来匹配现有服务
                # 仅在目标项目内查重：允许同一服务归属不同项目，便于按项目独立管理与导入测试
                dup_base = (
                    (AppService.func_desc == func_desc) &
                    (AppService.ip == ip) &
                    (AppService.program_path == program_path)
                )
                if project_id:
                    dup_base = dup_base & (AppService.project_id == project_id)
                existing = db.query(AppService).filter(dup_base).first()

                # 如果模块也提供了，也匹配模块
                if module and not existing:
                    dup_module = (
                        (AppService.func_desc == func_desc) &
                        (AppService.module == module) &
                        (AppService.ip == ip) &
                        (AppService.program_path == program_path)
                    )
                    if project_id:
                        dup_module = dup_module & (AppService.project_id == project_id)
                    existing = db.query(AppService).filter(dup_module).first()
                
                if existing:
                    # 重复数据跳过，但补全缺失的子系统/分类归属（不算覆盖更新）
                    old_project_id = existing.project_id
                    old_subsystem_id = existing.subsystem_id
                    old_group_id = existing.group_id
                    changed = False
                    if subsystem_id and not existing.subsystem_id:
                        existing.subsystem_id = subsystem_id
                        changed = True
                    if current_group_id and not existing.group_id:
                        existing.group_id = current_group_id
                        changed = True
                    if not existing.project_id and project_id:
                        existing.project_id = project_id
                        changed = True
                    if changed:
                        db.commit()
                        repaired += 1
                        repaired_ops.append({
                            'service_id': existing.id,
                            'old_project_id': old_project_id,
                            'old_subsystem_id': old_subsystem_id,
                            'old_group_id': old_group_id,
                        })
                    else:
                        skipped += 1
                    continue
                else:
                    # 计算 password
                    password = str(row.get('password', '')).strip()
                    
                    # 使用传入的项目ID，或者默认第一个项目
                    project = None
                    if project_id:
                        project = db.query(Project).filter(Project.id == project_id).first()
                    
                    if not project:
                        project = db.query(Project).first()
                    
                    if not project:
                        failed += 1
                        failed_items.append({
                            "row": idx + 2, 
                            "sheet": sheet_name, 
                            "reason": "系统中没有项目，无法创建服务",
                            "row_data": row
                        })
                        continue
                    
                    new_service = AppService(
                        project_id=project.id,
                        subsystem_id=subsystem_id,
                        group_id=current_group_id,
                        func_desc=func_desc,
                        module=str(row.get('module', '')).strip() or None,
                        ip=ip,
                        username=str(row.get('username', '')).strip() or 'root',
                        password=encrypt(password) if password else encrypt('password'),
                        program_path=program_path,
                        start_script=str(row.get('start_script', '')).strip() or None,
                        stop_script=str(row.get('stop_script', '')).strip() or None,
                        log_path=str(row.get('log_path', '')).strip() or None,
                        port=port_value,
                        owner=str(row.get('owner', '')).strip() or None,
                        remark=str(row.get('remark', '')).strip() or None,
                        # 自动判断部署方式和服务类型
                        deploy_type=deploy_type,
                        service_type=service_type,
                        # Docker相关字段
                        container_name=str(row.get('container_name', '')).strip() or None,
                        image_name=str(row.get('image_name', '')).strip() or None,
                        container_id=str(row.get('container_id', '')).strip() or None,
                        port_mapping=str(row.get('port_mapping', '')).strip() or None
                    )
                    
                    db.add(new_service)
                    db.commit()
                    added += 1
                    created_ids.append(new_service.id)
            except Exception as e:
                failed += 1
                failed_items.append({
                    "row": idx + 2, 
                    "sheet": sheet_name, 
                    "reason": f"导入失败: {str(e)}",
                    "row_data": row
                })


    # 导入完成后清除服务列表缓存 + 项目树缓存（关联/分组/子系统结构已变更）
    from utils.cache import invalidate_services_list, invalidate_projects_tree
    invalidate_services_list()
    invalidate_projects_tree()

    # ---------------- 落盘批次明细 ----------------
    try:
        op_rows = [ImportBatchOperation(
            batch_id=batch.id, op_type='created', service_id=sid
        ) for sid in created_ids]
        for op in repaired_ops:
            op_rows.append(ImportBatchOperation(
                batch_id=batch.id, op_type='repaired',
                service_id=op['service_id'],
                old_project_id=op['old_project_id'],
                old_subsystem_id=op['old_subsystem_id'],
                old_group_id=op['old_group_id'],
            ))
        if op_rows:
            db.add_all(op_rows)
        batch.added_count = added
        batch.repaired_count = repaired
        batch.skipped_count = skipped
        batch.failed_count = failed
        if auto_created_group_ids:
            batch.auto_created_group_ids = _json.dumps(auto_created_group_ids)
        db.commit()
        print(f"[import] batch {batch.batch_no}: added={added} repaired={repaired} ops={len(op_rows)}")
    except Exception as _batch_err:
        db.rollback()
        print(f"[import] save batch detail failed: {_batch_err}")

    # 导入完成后，把新增/补全归属的服务关联到同 IP 的在线 Agent，并通知 Agent 刷新采集清单。
    # 否则新服务 agent_uuid 为空（前端“Agent状态”显示“未关联”），且 Agent 内存清单未更新不会立即采集。
    try:
        affected_ids = list(created_ids) + [op.get('service_id') for op in repaired_ops if op.get('service_id')]
        await associate_services_to_online_agents(db, affected_ids)
    except Exception as _assoc_err:
        print(f"[import] associate services to agents failed: {_assoc_err}")

    log_audit(db, user.id, user.username, "SERVICE_IMPORT",
              result="success",
              output=f"导入完成: 新增{added}条, 跳过{skipped}条, 补全归属{repaired}条, 失败{failed}条")

    return ResponseModel(data={
        "success": True,
        "message": f"导入完成: 新增{added}条, 跳过{skipped}条, 补全归属{repaired}条, 失败{failed}条",
        "added": added,
        "skipped": skipped,
        "repaired": repaired,
        "failed": failed,
        "batch_no": batch.batch_no,
        "pre_backup_record_id": pre_snapshot_id,
        "failed_items": failed_items
    })

@router.get("/services/import/batches", response_model=ResponseModel)
async def list_import_batches(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_manage"))
):
    """服务端导入历史（支持撤销状态展示）"""
    from models.import_batch import ImportBatch
    from sqlalchemy import func
    total = db.query(func.count(ImportBatch.id))
    rows_q = db.query(ImportBatch)
    visible = get_visible_project_ids(db, user)
    if visible is not None:
        total = total.filter(ImportBatch.project_id.in_(visible))
        rows_q = rows_q.filter(ImportBatch.project_id.in_(visible))
    total = total.scalar()
    rows = (rows_q
            .order_by(ImportBatch.created_at.desc())
            .offset((page - 1) * size).limit(size).all())
    items = [{
        'batch_no': b.batch_no,
        'filename': b.filename,
        'project_id': b.project_id,
        'project_name': b.project_name,
        'added_count': b.added_count,
        'repaired_count': b.repaired_count,
        'skipped_count': b.skipped_count,
        'failed_count': b.failed_count,
        'status': b.status,
        'pre_backup_record_id': b.pre_backup_record_id,
        'created_by': b.created_by,
        'created_at': b.created_at.strftime('%Y-%m-%d %H:%M:%S') if b.created_at else None,
        'reverted_at': b.reverted_at.strftime('%Y-%m-%d %H:%M:%S') if b.reverted_at else None,
    } for b in rows]
    return ResponseModel(data={'items': items, 'total': total, 'page': page, 'size': size})


@router.post("/services/import/batches/{batch_no}/revert", response_model=ResponseModel)
async def revert_import_batch(
    batch_no: str,
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_manage"))
):
    """撤销一次导入：删除本批新增服务、还原归属补全、清理自动创建的空分类/子系统"""
    from models.import_batch import ImportBatch, ImportBatchOperation
    from models.subsystem_group_relation import SubsystemGroupRelation

    batch = db.query(ImportBatch).filter(ImportBatch.batch_no == batch_no).first()
    if not batch:
        raise HTTPException(status_code=404, detail="导入批次不存在")
    if batch.status == 'reverted':
        raise HTTPException(status_code=400, detail="该批次已撤销过，无法重复撤销")

    # DataScope：只能回滚有权限项目的导入批次
    assert_project_access(db, user, batch.project_id, detail="无权回滚该导入批次")

    ops = db.query(ImportBatchOperation).filter(
        ImportBatchOperation.batch_id == batch.id).all()
    created_ids = [o.service_id for o in ops if o.op_type == 'created']
    # DataScope：逐个校验本批新增服务的数据范围
    assert_services_access(db, user, created_ids)
    repaired_ops = [o for o in ops if o.op_type == 'repaired']

    deleted_count = 0
    restored_count = 0

    # 1. 删除本批新增的服务
    if created_ids:
        deleted_count = db.query(AppService).filter(
            AppService.id.in_(created_ids)).delete(synchronize_session=False)

    # 2. 还原补全归属的旧值
    for op in repaired_ops:
        svc = db.query(AppService).filter(AppService.id == op.service_id).first()
        if not svc:
            continue
        if op.old_subsystem_id is not None:
            svc.subsystem_id = op.old_subsystem_id
        if op.old_group_id is not None:
            svc.group_id = op.old_group_id
        if op.old_project_id is not None:
            svc.project_id = op.old_project_id
        db.commit()
        restored_count += 1

    # 3. 清理本次自动创建且已无服务的分类
    removed_groups = 0
    try:
        group_ids = _json.loads(batch.auto_created_group_ids or '[]')
    except Exception:
        group_ids = []
    for gid in group_ids or []:
        cnt = db.query(AppService).filter(AppService.group_id == gid).count()
        if cnt == 0:
            db.query(SubsystemGroupRelation).filter(
                SubsystemGroupRelation.group_id == gid).delete(synchronize_session=False)
            db.query(ServiceGroup).filter(ServiceGroup.id == gid).delete(synchronize_session=False)
            removed_groups += 1

    # 4. 清理本次自动创建且已无服务的默认子系统
    removed_default_subsystem = False
    if batch.default_subsystem_created and batch.subsystem_id:
        ss = db.query(Subsystem).filter(Subsystem.id == batch.subsystem_id).first()
        if ss:
            ss_services = db.query(AppService).filter(
                AppService.subsystem_id == ss.id).count()
            if ss_services == 0:
                db.query(SubsystemGroupRelation).filter(
                    SubsystemGroupRelation.subsystem_id == ss.id).delete(synchronize_session=False)
                db.delete(ss)
                removed_default_subsystem = True

    # 5. 清理本次导入在目标子系统下遗留的"子系统-分组"关联
    # 导入时会对每个 sheet 把分组关联到目标子系统，若该 sheet 所有服务被判
    # 重复跳过，仍会留下脏关联（尤其复用同名分组时跨项目借用分类）。
    # 这里删除"目标子系统下、已无任何服务引用"的关联行（仅删关联，不动全局分组）。
    removed_relations = 0
    if batch.subsystem_id:
        rels = db.query(SubsystemGroupRelation).filter(
            SubsystemGroupRelation.subsystem_id == batch.subsystem_id
        ).all()
        for rel in rels:
            used = db.query(AppService).filter(
                AppService.subsystem_id == batch.subsystem_id,
                AppService.group_id == rel.group_id
            ).count()
            if used == 0:
                db.delete(rel)
                removed_relations += 1

    batch.status = 'reverted'
    batch.reverted_at = datetime.now()
    batch.reverted_by = user.username
    db.commit()

    # 清缓存
    try:
        from utils.cache import invalidate_projects_tree, invalidate_services_list
        invalidate_projects_tree()
        invalidate_services_list()
    except Exception:
        pass

    log_audit(db, user.id, user.username, "IMPORT_REVERT",
              result="success",
              output=f"撤销导入批次 {batch_no}: 删除{deleted_count}条, 还原归属{restored_count}条, "
                     f"清理分类{removed_groups}个, 清理关联{removed_relations}条, 清理默认子系统{'1' if removed_default_subsystem else '0'}个")

    return ResponseModel(data={
        'batch_no': batch_no,
        'deleted_count': deleted_count,
        'restored_count': restored_count,
        'removed_groups': removed_groups,
        'removed_default_subsystem': removed_default_subsystem,
        'removed_relations': removed_relations,
        'pre_backup_record_id': batch.pre_backup_record_id,
    }, message="已撤销本次导入")


@router.post("/services/import/preview", response_model=ResponseModel)
async def preview_import_file(
    file: UploadFile = File(...),
    user = Depends(require_permission("service_manage"))
):
    """预览导入文件内容"""
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="只支持.xlsx格式的Excel文件")
    
    try:
        file_content = await file.read()
        wb = load_workbook(filename=io.BytesIO(file_content), read_only=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")
    
    # 获取第一个sheet的数据
    sheet_name = wb.sheetnames[0]
    ws = wb[sheet_name]
    
    # 读取表头
    headers = []
    for col in range(1, ws.max_column + 1):
        header = ws.cell(row=1, column=col).value
        headers.append(header.strip() if header else '')
    
    # 读取数据行（最多10行）
    rows = []
    max_rows = min(ws.max_row - 1, 10)
    for row in range(2, min(ws.max_row + 1, 12)):
        row_data = []
        for col in range(1, ws.max_column + 1):
            value = ws.cell(row=row, column=col).value
            row_data.append(value)
        rows.append(row_data)
    
    return ResponseModel(data={
        "headers": headers,
        "rows": rows,
        "sheet_name": sheet_name,
        "total_rows": ws.max_row - 1
    })

@router.get("/services/import/template")
async def download_import_template():
    """下载导入模板"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Service Import Template"
    
    # 添加表头
    headers = ["功能描述", "对应模块", "IP地址", "SSH端口", "用户名", "密码", 
               "程序路径", "启动脚本", "停止脚本", "日志路径", "端口", "部署方式",
               "容器名称", "镜像名称", "端口映射", "责任人", "备注"]
    ws.append(headers)
    
    # 在部署方式列表头添加注释说明
    ws.cell(row=1, column=12).comment = Comment("请从下拉框选择：主机部署 / Docker容器", "系统提示")
    
    # 添加示例数据（主机部署）
    ws.append(["示例服务1", "预处理", "192.168.1.1", "22", "root", "password", 
               "/opt/service/", "/opt/service/start.sh", "/opt/service/stop.sh", "/var/log/service/", "8080", "主机部署",
               "", "", "", "张三", "示例服务"])
    
    # 添加示例数据（Docker部署 - docker-compose方式）
    ws.append(["示例Docker服务(Compose)", "API模块", "192.168.1.101", "22", "root", "password", 
               "/opt/docker-app/", "docker-compose up -d", "docker-compose down", "", "8080", "Docker容器",
               "", "nginx:latest", "8080:80", "李四", "使用docker-compose部署"])
    
    # 添加示例数据（Docker部署 - 单容器方式）
    ws.append(["示例Docker服务(单容器)", "数据库模块", "192.168.1.102", "22", "root", "password", 
               "/opt/mysql/", "", "", "", "3306", "Docker容器",
               "mysql-container", "mysql:8.0", "3306:3306", "王五", "有容器名称时系统自动使用docker start/stop管理"])
    
    # 设置部署方式列的下拉框（第12列，从第2行开始）
    dv = DataValidation(
        type="list",
        formula1='"主机部署,Docker容器,Docker Compose"',
        allow_blank=False
    )
    ws.add_data_validation(dv)
    dv.add(f"L2:L100")
    
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    filename = "service_import_template.xlsx"
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


async def associate_services_to_online_agents(db: Session, service_ids: list = None):
    """
    把服务关联到同 IP 的在线 Agent，并通知相关 Agent 刷新服务清单。

    用于服务 Excel 导入 / 归属补全后：新建的服务 agent_uuid 为空，前端会显示“未关联”，
    且需要让对应 Agent 立即把新服务纳入采集。Agent 注册时虽会自动关联同 IP 服务，
    但导入发生在 Agent 已注册之后，不会触发重新关联，故在此主动补齐。

    Args:
        db: 数据库会话
        service_ids: 待处理的服务 ID 列表；为空则处理所有 agent_uuid 为空的服务
    """
    from models.app_service import AppService
    from models.agent import Agent
    from utils.redis_client import redis_client

    query = db.query(AppService)
    if service_ids is not None:
        if not service_ids:
            return
        services = query.filter(AppService.id.in_(service_ids)).all()
    else:
        services = query.filter(
            (AppService.agent_uuid == None) | (AppService.agent_uuid == "")
        ).all()

    # 在线 Agent 按其管理 IP 建立索引
    online_agents = db.query(Agent).filter(Agent.status == 'online').all()
    agent_by_ip = {a.ip: a for a in online_agents if a.ip}

    associated = 0
    for svc in services:
        if svc.agent_uuid:
            continue  # 已关联，跳过
        agent = agent_by_ip.get(svc.ip)
        if agent:
            svc.agent_uuid = agent.uuid
            associated += 1
            # 清除旧状态缓存，等待 Agent 重新上报
            redis_client.delete(f"service_status:{svc.id}")
            redis_client.delete(f"service_status_source:{svc.id}")

    if associated:
        db.commit()
        print(f"[associate] auto-associated {associated} imported services to online agents")

    # 通知所有相关在线 Agent 重新拉取服务清单（按 IP 匹配）
    await notify_agents_pull_services(db)


async def notify_agents_pull_services(db: Session, agent_uuid: str = None):
    """
    通知关联的在线 Agent 刷新服务列表。

    Args:
        db: 数据库会话
        agent_uuid: 指定 Agent UUID；若为 None 则根据 IP 查找所有关联的在线 Agent

    说明：服务更新（路径/部署类型/IP 等变更）或删除后，Agent 内存中的
         服务列表不会自动刷新，需要发送 pull_services 命令让 Agent 重新拉取。
         之前只在创建服务时发送，更新和删除场景漏掉了，导致在线编辑不生效。
    """
    from datetime import datetime

    # 如果没有指定 agent_uuid，通知所有在线 Agent 刷新服务列表
    if agent_uuid is None:
        from models.agent import Agent

        # 找出当前所有在线的 Agent
        online_agents = db.query(Agent).filter(Agent.status == 'online').all()
        if not online_agents:
            return

        # 不能用 Agent.ip 与 AppService.ip 匹配来筛选目标 Agent：
        # agent.ip 是 Agent 自身所在机器的 IP，服务可能部署在 Agent 管理的其他机器上，
        # 两者不相等时会被漏掉，导致配置变更通知不到对应 Agent。
        # 服务与 Agent 的关联关系以 app_services.agent_uuid 为准，这里直接通知全部在线 Agent，
        # 由 Agent 拉取时按 agent_uuid 取自己名下的服务（数量有限，开销可接受）。
        target_uuids = {a.uuid for a in online_agents}
    else:
        if not agent_uuid:
            return
        target_uuids = {agent_uuid}

    # 发送 pull_services 消息
    try:
        from api.agent import manager
        from models.agent import Agent

        # 用软在线判断（WebSocket 连接 或 30s 内有心跳）。
        # 只查 active_connections 会漏掉"后端刚重启、Agent 尚未重连"的情况，
        # 导致通知被静默跳过，服务配置变更要等 Agent 重启才生效。
        agent_map = {
            a.uuid: a for a in db.query(Agent).filter(Agent.uuid.in_(target_uuids)).all()
        }
        for uuid in target_uuids:
            agent = agent_map.get(uuid)
            if not manager.is_online(uuid, agent.last_heartbeat if agent else None):
                continue
            pull_message = {
                "type": "pull_services",
                "request_id": "",
                "timestamp": datetime.now().timestamp(),
                "data": {}
            }
            ok = await manager.send_message(uuid, pull_message)
            if not ok:
                import logging
                logging.getLogger(__name__).warning(
                    f"notify_agents_pull_services: send to {uuid} failed (connection gone)"
                )
    except Exception as e:
        # 通知失败不影响主流程
        import logging
        logging.getLogger(__name__).warning(f"notify_agents_pull_services failed: {e}")
