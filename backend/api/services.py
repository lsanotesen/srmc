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
from utils.program_status import get_program_status, get_batch_program_status
from services.audit_service import log_audit
from core.database import get_db
from api.dependencies import get_current_user, require_permission
from utils.ssh_pool import ssh_pool
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment
from typing import List, Optional
import asyncio
import io

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
        print(f"[Agent Op] action={action}, service_id={service.id}, initial_agent_uuid={agent_uuid}")
        
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
                    return None
        
        agent = db.query(Agent).filter(Agent.uuid == agent_uuid).first()
        
        if not agent:
            print(f"[Agent Op] Agent not found in DB: {agent_uuid}")
            return None
        
        print(f"[Agent Op] Agent IP check: service.ip={service.ip}, agent.ip={agent.ip}")
        if service.ip != agent.ip:
            print(f"[Agent Op] Service IP mismatch, skipping agent operation")
            return None
        
        print(f"[Agent Op] Sending command to agent {agent_uuid}...")
        result = await manager.send_command_with_response(
            agent_uuid,
            str(service.id),
            action,
            service,
            timeout=30
        )
        print(f"[Agent Op] Command result: {result}")
        return result
    except Exception as e:
        print(f"[Agent Op] Agent operation failed: {e}")
        return None
    finally:
        db.close()

@router.get("/services/list", response_model=ResponseModel)
async def list_services(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    services = db.query(AppService).all()
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
    func_desc: str = Query(None),
    module: str = Query(None),
    ip: str = Query(None),
    owner: str = Query(None),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    from models.subsystem import Subsystem
    from models.service_group import ServiceGroup
    
    query = db.query(AppService, Project, Subsystem, ServiceGroup).\
        outerjoin(Project, AppService.project_id == Project.id).\
        outerjoin(Subsystem, AppService.subsystem_id == Subsystem.id).\
        outerjoin(ServiceGroup, AppService.group_id == ServiceGroup.id)
    
    if project_id:
        query = query.filter(AppService.project_id == project_id)
    if subsystem_id:
        query = query.filter(AppService.subsystem_id == subsystem_id)
    if group_id:
        query = query.filter(AppService.group_id == group_id)
    if deploy_type:
        query = query.filter(AppService.deploy_type == deploy_type)
    if func_desc:
        query = query.filter(AppService.func_desc.like(f"%{func_desc}%"))
    if module:
        query = query.filter(AppService.module.like(f"%{module}%"))
    if ip:
        query = query.filter(AppService.ip.like(f"%{ip}%"))
    if owner:
        query = query.filter(AppService.owner.like(f"%{owner}%"))
    
    total = query.count()
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
    
    return ResponseModel(data={"items": result, "total": total, "page": page, "size": size})

@router.get("/services/count", response_model=ResponseModel)
async def count_services(
    project_id: int = Query(None, ge=1),
    subsystem_id: int = Query(None, ge=1),
    group_id: int = Query(None, ge=1),
    deploy_type: str = Query(None),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    query = db.query(AppService)
    
    if project_id:
        query = query.filter(AppService.project_id == project_id)
    if subsystem_id:
        query = query.filter(AppService.subsystem_id == subsystem_id)
    if group_id:
        query = query.filter(AppService.group_id == group_id)
    if deploy_type:
        query = query.filter(AppService.deploy_type == deploy_type)
    
    total = query.count()
    return ResponseModel(data=total)

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
    
    project = db.query(Project).filter(Project.id == service.project_id).first()
    subsystem = db.query(Subsystem).filter(Subsystem.id == service.subsystem_id).first() if service.subsystem_id else None
    service_group = db.query(ServiceGroup).filter(ServiceGroup.id == service.group_id).first() if service.group_id else None

    # 从 Redis 读取当前状态和容器详情（用于 Docker Compose 服务的 Partial 状态展示）
    import json
    from utils.redis_client import redis_client
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
    
    from models.agent import Agent
    online_agent = db.query(Agent).filter(
        Agent.ip == new_service.ip,
        Agent.status == 'online'
    ).first()
    
    if online_agent:
        new_service.agent_uuid = online_agent.uuid
        db.commit()
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
    
    if service_update.project_id is not None:
        project = db.query(Project).filter(Project.id == service_update.project_id).first()
        if not project:
            raise HTTPException(status_code=400, detail="项目不存在")
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
    
    project = db.query(Project).filter(Project.id == service.project_id).first()
    subsystem = db.query(Subsystem).filter(Subsystem.id == service.subsystem_id).first() if service.subsystem_id else None
    service_group = db.query(ServiceGroup).filter(ServiceGroup.id == service.group_id).first() if service.group_id else None
    
    log_audit(db, user.id, user.username, "SERVICE_UPDATE", 
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
    
    func_desc = service.func_desc
    db.delete(service)
    db.commit()
    
    log_audit(db, user.id, user.username, "SERVICE_DELETE", 
              result="success", output=f"删除服务: {func_desc}")
    
    return ResponseModel(data={"id": service_id})

@router.post("/services/batch/delete", response_model=ResponseModel)
async def batch_delete_services(
    service_ids: List[int],
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_manage"))
):
    if not service_ids:
        raise HTTPException(status_code=400, detail="请选择要删除的服务")
    
    # 使用批量删除，提高性能
    deleted_count = db.query(AppService).filter(AppService.id.in_(service_ids)).delete(synchronize_session=False)
    
    if deleted_count > 0:
        db.commit()
        log_audit(db, user.id, user.username, "SERVICE_DELETE", 
                  result="success", output=f"批量删除服务 {deleted_count} 个")
    
    return ResponseModel(data={"deleted": deleted_count})

@router.post("/services/status/batch", response_model=ResponseModel)
async def batch_get_status(
    service_ids: List[int],
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    if not service_ids:
        return ResponseModel(data={})
    
    services = db.query(AppService).filter(AppService.id.in_(service_ids)).all()
    progs = []
    for service in services:
        progs.append({
            'id': service.id,
            'ip': service.ip,
            'username': service.username,
            'password': decrypt(service.password),
            'port': service.port,
            'program_path': service.program_path,
            'deploy_type': service.deploy_type,
            'container_name': service.container_name,
            'ssh_port': service.ssh_port or 22
        })
    
    result = await get_batch_program_status(progs)
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
                    'source': source.decode('utf-8') if source else 'SSH'
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
                  result="success" if success else "partial",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 类型: {service_type}, 命令: {command}, 输出: {output[:200]}")
        
        return ResponseModel(data={"success": success, "message": result_message, "output": output[:500]})
    except Exception as e:
        log_audit(db, user.id, user.username, "SERVICE_START",
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
                  result="success" if success else "partial",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 类型: {service_type}, 命令: {command}, 输出: {output[:200]}")
        
        return ResponseModel(data={"success": success, "message": result_message, "output": output[:500]})
    except Exception as e:
        log_audit(db, user.id, user.username, "SERVICE_STOP",
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
                  result="success" if success else "partial",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 类型: {service_type}, 输出: {output[:200]}")
        
        return ResponseModel(data={"success": success, "message": result_message, "output": output[:500]})
    except Exception as e:
        log_audit(db, user.id, user.username, "SERVICE_RESTART",
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
async def service_log_websocket(websocket: WebSocket, service_id: int, db: Session = Depends(get_db)):
    await websocket.accept()
    
    service = db.query(AppService).filter(AppService.id == service_id).first()
    if not service:
        await websocket.send_json({"type": "error", "message": "服务不存在"})
        await websocket.close()
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
    
    # 打印调试信息
    print(f"Available groups: {list(group_name_to_id.keys())}")
    print(f"Sheet names: {wb.sheetnames}")
    
    added = 0
    updated = 0
    failed = 0
    failed_items = []
    
    # 遍历所有 sheet
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        
        # 根据 sheet 名称匹配分类（支持多种匹配方式）
        matched_group_id = None
        sheet_name_clean = sheet_name.strip()
        
        # 1. 精确匹配
        if sheet_name_clean in group_name_to_id:
            matched_group_id = group_name_to_id[sheet_name_clean]
        else:
            # 2. 忽略大小写匹配
            sheet_name_lower = sheet_name_clean.lower()
            for group_name, group_id in group_name_to_id.items():
                if group_name.lower() == sheet_name_lower:
                    matched_group_id = group_id
                    break
        
        # 3. 模糊匹配：检查分类名称是否包含sheet名称（如"预处理程序"包含"预处理"）
        if not matched_group_id:
            for group_name, group_id in group_name_to_id.items():
                if sheet_name_clean in group_name or sheet_name_lower in group_name.lower():
                    matched_group_id = group_id
                    break
        
        # 4. 模糊匹配：检查sheet名称是否包含分类名称
        if not matched_group_id:
            for group_name, group_id in group_name_to_id.items():
                group_name_clean = group_name.strip()
                if group_name_clean in sheet_name_clean or group_name_clean.lower() in sheet_name_lower:
                    matched_group_id = group_id
                    break
        
        if matched_group_id:
            # 使用匹配到的分类
            current_group_id = matched_group_id
            print(f"Sheet '{sheet_name}' matched to group '{list(group_name_to_id.keys())[list(group_name_to_id.values()).index(matched_group_id)]}' (ID: {matched_group_id})")
        else:
            # 没有匹配到分类，使用传入的 group_id（如果有），否则不设置分类
            current_group_id = group_id
            print(f"Sheet '{sheet_name}' no group matched, using default group_id: {group_id}")
        
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
                    normalized_ports = port_raw.replace('，', ',').replace(';', ',').replace('；', ',')
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
                existing = db.query(AppService).filter(
                    (AppService.func_desc == func_desc) &
                    (AppService.ip == ip) &
                    (AppService.program_path == program_path)
                ).first()
                
                # 如果模块也提供了，也匹配模块
                if module and not existing:
                    existing = db.query(AppService).filter(
                        (AppService.func_desc == func_desc) &
                        (AppService.module == module) &
                        (AppService.ip == ip) &
                        (AppService.program_path == program_path)
                    ).first()
                
                password = str(row.get('password', '')).strip()
                
                if existing:
                    if 'module' in row:
                        existing.module = str(row.get('module', '')).strip() or None
                    if 'username' in row:
                        existing.username = str(row.get('username', '')).strip()
                    if password:
                        existing.password = encrypt(password)
                    if 'start_script' in row:
                        existing.start_script = str(row.get('start_script', '')).strip() or None
                    if 'stop_script' in row:
                        existing.stop_script = str(row.get('stop_script', '')).strip() or None
                    if 'log_path' in row:
                        existing.log_path = str(row.get('log_path', '')).strip() or None
                    if port_value:
                        existing.port = port_value
                    if 'owner' in row:
                        existing.owner = str(row.get('owner', '')).strip() or None
                    if 'remark' in row:
                        existing.remark = str(row.get('remark', '')).strip() or None
                    
                    db.commit()
                    updated += 1
                else:
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
            except Exception as e:
                failed += 1
                failed_items.append({
                    "row": idx + 2, 
                    "sheet": sheet_name, 
                    "reason": f"导入失败: {str(e)}",
                    "row_data": row
                })
    
    log_audit(db, user.id, user.username, "SERVICE_IMPORT",
              result="success", 
              output=f"导入完成: 新增{added}条, 更新{updated}条, 失败{failed}条")
    
    return ResponseModel(data={
        "success": True,
        "message": f"导入完成: 新增{added}条, 更新{updated}条, 失败{failed}条",
        "added": added,
        "updated": updated,
        "failed": failed,
        "failed_items": failed_items
    })

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