from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from models.audit_log import AuditLog
from schemas.common import ResponseModel
from core.database import get_db
from api.dependencies import require_permission

router = APIRouter()

def log_to_dict(log: AuditLog):
    return {
        "id": log.id,
        "user_id": log.user_id,
        "username": log.username,
        "action": log.action,
        "service_id": log.service_id,
        "service_code": log.service_code,
        "server_id": log.server_id,
        "ip": log.ip,
        "result": log.result,
        "output": log.output,
        "duration": log.duration,
        "created_at": log.created_at.isoformat() if log.created_at else None
    }

@router.get("/audit/logs", response_model=ResponseModel)
async def get_audit_logs_short(
    limit: int = Query(5, ge=1, le=100),
    db: Session = Depends(get_db),
    user = Depends(require_permission("audit_view"))
):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    logs_dict = [log_to_dict(log) for log in logs]
    return ResponseModel(data=logs_dict)

@router.get("/audit", response_model=ResponseModel)
async def get_audit_logs(
    user_id: int = Query(None),
    action: str = Query(None),
    service_code: str = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user = Depends(require_permission("audit_view"))
):
    query = db.query(AuditLog)
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if service_code:
        query = query.filter(AuditLog.service_code == service_code)
    if start_time:
        query = query.filter(AuditLog.created_at >= start_time)
    if end_time:
        query = query.filter(AuditLog.created_at <= end_time)
    
    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    logs_dict = [log_to_dict(log) for log in logs]
    
    return ResponseModel(data={
        "items": logs_dict,
        "total": total,
        "page": page,
        "limit": limit
    })
