from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, WebSocket, WebSocketDisconnect, Form, Request, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from urllib.parse import quote
from models.app_service import AppService
from models.project import Project
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
    """获取脚本路径，如果没有./前缀则自动添加"""
    if script.startswith('./') or script.startswith('/') or script.startswith('~'):
        return script
    return f"./{script}"

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
            'service_type': service.module,
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
            'status': None,
            'created_at': service.created_at,
            'updated_at': service.updated_at
        })
    
    return ResponseModel(data={"items": result, "total": total, "page": page, "size": size})

@router.get("/services/template")
async def download_service_template(
    user = Depends(require_permission("service_manage"))
):
    """下载服务导入模板"""
    headers = ['功能描述', '对应模块', 'IP地址', '用户名', '密码', 
               '程序路径', '启动脚本', '停止脚本', '日志路径', '端口', '责任人', '备注']
    
    wb = Workbook()
    ws = wb.active
    ws.title = "服务导入模板"
    
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
    
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=services_template.xlsx"}
    )


@router.get("/services/export")
async def export_services(
    project_id: int = Query(None, ge=1),
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_manage"))
):
    query = db.query(AppService, Project).outerjoin(Project, AppService.project_id == Project.id)
    if project_id:
        query = query.filter(AppService.project_id == project_id)
    
    results = query.all()
    
    headers = ['project_name', 'func_desc', 'module', 'ip', 'username', 'password', 
               'program_path', 'start_script', 'stop_script', 'log_path', 'port', 'owner', 'remark']
    
    wb = Workbook()
    ws = wb.active
    ws.title = "服务列表"
    
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
    
    for row_idx, (service, project) in enumerate(results, 2):
        ws.cell(row=row_idx, column=1, value=project.name if project else '')
        ws.cell(row=row_idx, column=2, value=service.func_desc)
        ws.cell(row=row_idx, column=3, value=service.module or '')
        ws.cell(row=row_idx, column=4, value=service.ip)
        ws.cell(row=row_idx, column=5, value=service.username)
        ws.cell(row=row_idx, column=6, value='')
        ws.cell(row=row_idx, column=7, value=service.program_path)
        ws.cell(row=row_idx, column=8, value=service.start_script or '')
        ws.cell(row=row_idx, column=9, value=service.stop_script or '')
        ws.cell(row=row_idx, column=10, value=service.log_path or '')
        ws.cell(row=row_idx, column=11, value=service.port or '')
        ws.cell(row=row_idx, column=12, value=service.owner or '')
        ws.cell(row=row_idx, column=13, value=service.remark or '')
    
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=services.xlsx"}
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
        'status': None,
        'created_at': service.created_at,
        'updated_at': service.updated_at
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
        port=service_create.port,
        owner=service_create.owner,
        remark=service_create.remark
    )
    
    db.add(new_service)
    db.commit()
    
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
        'status': None,
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
            'program_path': service.program_path
        })
    
    result = await get_batch_program_status(progs)
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
    
    if not service.start_script:
        return ResponseModel(data={"success": False, "message": "未配置启动脚本"}, code=400)
    
    try:
        ssh = await ssh_pool.get_connection(service.ip, service.ssh_port or 22, service.username, decrypt(service.password))
        if not ssh:
            return ResponseModel(data={"success": False, "message": "无法建立SSH连接"}, code=500)
        
        command = f"cd {expand_home_path(service.program_path)} && {get_script_path(service.start_script)}"
        output, error, success = await ssh.execute_command(command)
        
        ssh.close()
        
        await asyncio.sleep(2)
        
        status = await get_program_status(service.ip, service.username, decrypt(service.password), service.port, service.program_path, service.ssh_port or 22)
        
        success = status == "RUNNING"
        message = "启动成功" if success else "启动命令已执行，请检查状态"
        
        log_audit(db, user.id, user.username, "SERVICE_START",
                  result="success" if success else "partial",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 输出: {output[:200]}")
        
        return ResponseModel(data={"success": success, "message": message, "output": output[:500]})
    except Exception as e:
        log_audit(db, user.id, user.username, "SERVICE_START",
                  result="failed",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 错误: {str(e)}")
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
    
    if not service.stop_script:
        return ResponseModel(data={"success": False, "message": "未配置停止脚本"}, code=400)
    
    try:
        ssh = await ssh_pool.get_connection(service.ip, service.ssh_port or 22, service.username, decrypt(service.password))
        if not ssh:
            return ResponseModel(data={"success": False, "message": "无法建立SSH连接"}, code=500)
        
        command = f"cd {expand_home_path(service.program_path)} && {get_script_path(service.stop_script)}"
        output, error, cmd_success = await ssh.execute_command(command)
        
        ssh.close()
        
        await asyncio.sleep(2)
        
        status = await get_program_status(service.ip, service.username, decrypt(service.password), service.port, service.program_path, service.ssh_port or 22)
        
        stopped = status == "STOPPED"
        message = "停止成功" if stopped else "停止命令已执行，请检查状态"
        
        log_audit(db, user.id, user.username, "SERVICE_STOP",
                  result="success" if stopped else "partial",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 输出: {output[:200]}, 错误: {error[:200]}")
        
        return ResponseModel(data={"success": stopped, "message": message, "output": output[:500]})
    except Exception as e:
        log_audit(db, user.id, user.username, "SERVICE_STOP",
                  result="failed",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 错误: {str(e)}")
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
    
    try:
        ssh = await ssh_pool.get_connection(service.ip, service.ssh_port or 22, service.username, decrypt(service.password))
        if not ssh:
            return ResponseModel(data={"success": False, "message": "无法建立SSH连接"}, code=500)
        
        if service.stop_script:
            command = f"cd {expand_home_path(service.program_path)} && {get_script_path(service.stop_script)}"
            await ssh.execute_command(command)
            await asyncio.sleep(1)
        
        if service.start_script:
            command = f"cd {expand_home_path(service.program_path)} && {get_script_path(service.start_script)}"
            output, error, success = await ssh.execute_command(command)
        else:
            output = "未配置启动脚本"
        
        ssh.close()
        
        await asyncio.sleep(2)
        
        status = await get_program_status(service.ip, service.username, decrypt(service.password), service.port, service.program_path, service.ssh_port or 22)
        
        success = status == "RUNNING"
        message = "重启成功" if success else "重启命令已执行，请检查状态"
        
        log_audit(db, user.id, user.username, "SERVICE_RESTART",
                  result="success" if success else "partial",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 输出: {output[:200]}")
        
        return ResponseModel(data={"success": success, "message": message, "output": output[:500]})
    except Exception as e:
        log_audit(db, user.id, user.username, "SERVICE_RESTART",
                  result="failed",
                  output=f"服务: {service.func_desc}, IP: {service.ip}, 错误: {str(e)}")
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
    
    if not service.log_path:
        return ResponseModel(data={"files": [], "message": "未配置日志路径"}, code=400)
    
    try:
        ssh = await ssh_pool.get_connection(service.ip, service.ssh_port or 22, service.username, decrypt(service.password))
        if not ssh:
            return ResponseModel(data={"files": [], "message": "无法建立SSH连接"}, code=500)
        
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
    
    if not service.log_path:
        return ResponseModel(data={"content": "未配置日志路径"}, code=400)
    
    try:
        ssh = await ssh_pool.get_connection(service.ip, service.ssh_port or 22, service.username, decrypt(service.password))
        if not ssh:
            return ResponseModel(data={"content": "无法建立SSH连接"}, code=500)
        
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
        'remark': 'remark'
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
            ('负责', 'owner'),
            ('责任', 'owner'),
            ('备注', 'remark'),
        ]:
            if keyword in header_str:
                return field
        return None
    
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
                
                # 收集缺失的必填字段
                missing_fields = []
                if not func_desc:
                    missing_fields.append('功能描述')
                if not ip:
                    missing_fields.append('IP地址')
                if not program_path:
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
                        remark=str(row.get('remark', '')).strip() or None
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
    ws.title = "服务导入模板"
    
    # 添加表头
    headers = ["功能描述", "对应模块", "IP地址", "程序路径", "用户名", "密码", 
               "启动脚本", "停止脚本", "日志路径", "端口", "责任人", "备注"]
    ws.append(headers)
    
    # 添加示例数据
    ws.append(["示例服务1", "预处理", "192.168.1.1", "/opt/service1.sh", "root", "", 
               "/opt/service1.sh start", "/opt/service1.sh stop", "/var/log/service1.log", "8080", "张三", "示例服务"])
    
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=服务导入模板.xlsx"}
    )