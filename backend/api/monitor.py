import asyncio
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from models.service import Service
from schemas.monitor import ServiceStatusResponse, BatchStatusResponse
from schemas.common import ResponseModel
from services.monitor_service import get_service_status, update_all_service_statuses
from core.database import get_db
from api.dependencies import require_permission

router = APIRouter()

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
    await update_all_service_statuses(db)
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
