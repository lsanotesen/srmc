from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from models.process import Process
from models.project import Project
from schemas.process import ProcessCreate, ProcessUpdate, ProcessResponse
from schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from schemas.common import ResponseModel
from services.monitor_service import start_process, stop_process, restart_process, check_process_status
from services.audit_service import log_audit
from core.database import get_db
from api.dependencies import get_current_user, require_permission
from typing import List
import pandas as pd
import io

router = APIRouter()

@router.get("/processes", response_model=ResponseModel)
async def get_processes(
    project_id: int = None,
    language: str = None,
    status: str = None,
    keyword: str = None,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    query = db.query(Process).outerjoin(Project, Process.project_id == Project.id)

    if project_id:
        query = query.filter(Process.project_id == project_id)
    if language:
        query = query.filter(Process.language == language)
    if status:
        query = query.filter(Process.status == status)
    if keyword:
        query = query.filter(
            (Process.process_name.ilike(f"%{keyword}%")) |
            (Process.process_code.ilike(f"%{keyword}%"))
        )

    processes = query.all()

    result = []
    for p in processes:
        p_dict = p.__dict__.copy()
        p_dict.pop('_sa_instance_state', None)
        p_dict['project_name'] = p.project.name if p.project else None
        result.append(p_dict)

    return ResponseModel(data=result)

@router.get("/processes/{process_id}", response_model=ResponseModel)
async def get_process(process_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    process = db.query(Process).filter(Process.id == process_id).first()
    if not process:
        raise HTTPException(status_code=404, detail="程序不存在")

    result = process.__dict__.copy()
    result.pop('_sa_instance_state', None)
    result['project_name'] = process.project.name if process.project else None

    return ResponseModel(data=result)

@router.post("/processes", response_model=ResponseModel)
async def create_process(process: ProcessCreate, db: Session = Depends(get_db), user = Depends(require_permission("service_manage"))):
    existing = db.query(Process).filter(Process.process_code == process.process_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="程序编码已存在")

    new_process = Process(
        process_name=process.process_name,
        process_code=process.process_code,
        project_id=process.project_id,
        language=process.language,
        module=process.module,
        environment=process.environment,
        ip=process.ip,
        port=process.port,
        work_dir=process.work_dir,
        start_command=process.start_command,
        stop_command=process.stop_command,
        check_type=process.check_type,
        check_keyword=process.check_keyword,
        owner=process.owner,
        remark=process.remark
    )
    db.add(new_process)
    db.commit()

    log_audit(db, user.id, user.username, "CREATE_PROCESS", result="success", output=f"Created process: {process.process_name}")

    return ResponseModel(data=new_process)

@router.put("/processes/{process_id}", response_model=ResponseModel)
async def update_process(process_id: int, process: ProcessUpdate, db: Session = Depends(get_db), user = Depends(require_permission("service_manage"))):
    process_to_update = db.query(Process).filter(Process.id == process_id).first()
    if not process_to_update:
        raise HTTPException(status_code=404, detail="程序不存在")

    if process.process_name:
        process_to_update.process_name = process.process_name
    if process.project_id is not None:
        process_to_update.project_id = process.project_id
    if process.language:
        process_to_update.language = process.language
    if process.module:
        process_to_update.module = process.module
    if process.environment:
        process_to_update.environment = process.environment
    if process.ip:
        process_to_update.ip = process.ip
    if process.port:
        process_to_update.port = process.port
    if process.work_dir:
        process_to_update.work_dir = process.work_dir
    if process.start_command:
        process_to_update.start_command = process.start_command
    if process.stop_command:
        process_to_update.stop_command = process.stop_command
    if process.check_type:
        process_to_update.check_type = process.check_type
    if process.check_keyword:
        process_to_update.check_keyword = process.check_keyword
    if process.owner:
        process_to_update.owner = process.owner
    if process.remark:
        process_to_update.remark = process.remark

    db.commit()

    log_audit(db, user.id, user.username, "UPDATE_PROCESS", result="success", output=f"Updated process: {process_to_update.process_name}")

    return ResponseModel(data=process_to_update)

@router.delete("/processes/{process_id}", response_model=ResponseModel)
async def delete_process(process_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_manage"))):
    process = db.query(Process).filter(Process.id == process_id).first()
    if not process:
        raise HTTPException(status_code=404, detail="程序不存在")

    db.delete(process)
    db.commit()

    log_audit(db, user.id, user.username, "DELETE_PROCESS", result="success", output=f"Deleted process: {process.process_name}")

    return ResponseModel(message="程序删除成功")

@router.post("/processes/{process_id}/start", response_model=ResponseModel)
async def start_process_api(process_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_control"))):
    process = db.query(Process).filter(Process.id == process_id).first()
    if not process:
        raise HTTPException(status_code=404, detail="程序不存在")

    try:
        result = start_process(process)
        if result:
            process.status = 'RUNNING'
            db.commit()
            log_audit(db, user.id, user.username, "START_PROCESS", result="success", output=f"Started process: {process.process_name}")
            return ResponseModel(message="启动成功")
        else:
            log_audit(db, user.id, user.username, "START_PROCESS", result="failed", output=f"Failed to start process: {process.process_name}")
            return ResponseModel(code=1, message="启动失败")
    except Exception as e:
        log_audit(db, user.id, user.username, "START_PROCESS", result="failed", output=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/processes/{process_id}/stop", response_model=ResponseModel)
async def stop_process_api(process_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_control"))):
    process = db.query(Process).filter(Process.id == process_id).first()
    if not process:
        raise HTTPException(status_code=404, detail="程序不存在")

    try:
        result = stop_process(process)
        if result:
            process.status = 'STOPPED'
            db.commit()
            log_audit(db, user.id, user.username, "STOP_PROCESS", result="success", output=f"Stopped process: {process.process_name}")
            return ResponseModel(message="停止成功")
        else:
            log_audit(db, user.id, user.username, "STOP_PROCESS", result="failed", output=f"Failed to stop process: {process.process_name}")
            return ResponseModel(code=1, message="停止失败")
    except Exception as e:
        log_audit(db, user.id, user.username, "STOP_PROCESS", result="failed", output=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/processes/{process_id}/restart", response_model=ResponseModel)
async def restart_process_api(process_id: int, db: Session = Depends(get_db), user = Depends(require_permission("service_control"))):
    process = db.query(Process).filter(Process.id == process_id).first()
    if not process:
        raise HTTPException(status_code=404, detail="程序不存在")

    try:
        result = restart_process(process)
        if result:
            process.status = 'RUNNING'
            db.commit()
            log_audit(db, user.id, user.username, "RESTART_PROCESS", result="success", output=f"Restarted process: {process.process_name}")
            return ResponseModel(message="重启成功")
        else:
            log_audit(db, user.id, user.username, "RESTART_PROCESS", result="failed", output=f"Failed to restart process: {process.process_name}")
            return ResponseModel(code=1, message="重启失败")
    except Exception as e:
        log_audit(db, user.id, user.username, "RESTART_PROCESS", result="failed", output=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/processes/batch/start", response_model=ResponseModel)
async def batch_start_processes(process_ids: List[int], db: Session = Depends(get_db), user = Depends(require_permission("service_control"))):
    success_count = 0
    fail_count = 0

    for pid in process_ids:
        process = db.query(Process).filter(Process.id == pid).first()
        if process:
            try:
                result = start_process(process)
                if result:
                    process.status = 'RUNNING'
                    success_count += 1
                else:
                    fail_count += 1
            except:
                fail_count += 1

    db.commit()
    log_audit(db, user.id, user.username, "BATCH_START_PROCESS", result="success", output=f"Batch started: {success_count} success, {fail_count} failed")

    return ResponseModel(data={"success": success_count, "failed": fail_count})

@router.post("/processes/batch/stop", response_model=ResponseModel)
async def batch_stop_processes(process_ids: List[int], db: Session = Depends(get_db), user = Depends(require_permission("service_control"))):
    success_count = 0
    fail_count = 0

    for pid in process_ids:
        process = db.query(Process).filter(Process.id == pid).first()
        if process:
            try:
                result = stop_process(process)
                if result:
                    process.status = 'STOPPED'
                    success_count += 1
                else:
                    fail_count += 1
            except:
                fail_count += 1

    db.commit()
    log_audit(db, user.id, user.username, "BATCH_STOP_PROCESS", result="success", output=f"Batch stopped: {success_count} success, {fail_count} failed")

    return ResponseModel(data={"success": success_count, "failed": fail_count})

@router.post("/processes/batch/restart", response_model=ResponseModel)
async def batch_restart_processes(process_ids: List[int], db: Session = Depends(get_db), user = Depends(require_permission("service_control"))):
    success_count = 0
    fail_count = 0

    for pid in process_ids:
        process = db.query(Process).filter(Process.id == pid).first()
        if process:
            try:
                result = restart_process(process)
                if result:
                    process.status = 'RUNNING'
                    success_count += 1
                else:
                    fail_count += 1
            except:
                fail_count += 1

    db.commit()
    log_audit(db, user.id, user.username, "BATCH_RESTART_PROCESS", result="success", output=f"Batch restarted: {success_count} success, {fail_count} failed")

    return ResponseModel(data={"success": success_count, "failed": fail_count})

@router.get("/import/processes/template")
async def download_process_template():
    columns = [
        'process_name', 'process_code', 'project_name', 'language',
        'module', 'environment', 'ip', 'port', 'work_dir',
        'start_command', 'stop_command', 'check_type', 'check_keyword', 'owner', 'remark'
    ]
    df = pd.DataFrame(columns=columns)
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer

@router.post("/import/processes", response_model=ResponseModel)
async def import_processes(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user = Depends(require_permission("service_manage"))
):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="仅支持xlsx格式文件")

    try:
        df = pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")

    added = 0
    updated = 0
    failed = 0

    for _, row in df.iterrows():
        try:
            process_code = str(row.get('process_code', '')).strip()
            if not process_code:
                failed += 1
                continue

            existing = db.query(Process).filter(Process.process_code == process_code).first()

            project_name = str(row.get('project_name', '')).strip()
            project_id = None
            if project_name:
                project = db.query(Project).filter(Project.name == project_name).first()
                if project:
                    project_id = project.id

            process_data = {
                'process_name': str(row.get('process_name', '')).strip(),
                'language': str(row.get('language', 'JAVA')).strip(),
                'module': str(row.get('module', '')).strip(),
                'environment': str(row.get('environment', 'DEV')).strip(),
                'ip': str(row.get('ip', '')).strip(),
                'port': int(row.get('port')) if pd.notna(row.get('port')) else None,
                'work_dir': str(row.get('work_dir', '')).strip(),
                'start_command': str(row.get('start_command', '')).strip(),
                'stop_command': str(row.get('stop_command', '')).strip(),
                'check_type': str(row.get('check_type', 'PROCESS')).strip(),
                'check_keyword': str(row.get('check_keyword', '')).strip(),
                'owner': str(row.get('owner', '')).strip(),
                'remark': str(row.get('remark', '')).strip(),
                'project_id': project_id
            }

            if existing:
                for key, value in process_data.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                new_process = Process(process_code=process_code, **process_data)
                db.add(new_process)
                added += 1
        except Exception:
            failed += 1

    db.commit()
    log_audit(db, user.id, user.username, "IMPORT_PROCESSES", result="success", output=f"Imported: {added} added, {updated} updated, {failed} failed")

    return ResponseModel(data={"added": added, "updated": updated, "failed": failed})
