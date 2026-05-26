from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from models.audit_log import AuditLog
from schemas.common import ResponseModel
from core.database import get_db
from api.dependencies import require_permission

router = APIRouter()

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
    
    return ResponseModel(data={
        "items": logs,
        "total": total,
        "page": page,
        "limit": limit
    })
