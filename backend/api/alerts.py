"""告警中心接口（基础版）

权限：查看复用 service:view；确认/恢复复用 service_operate
（legacy 别名 → service:start|service:stop|service:restart），不新增权限码。
数据范围：复用 DataScopeService（含 ProjectMember / ProjectPermission）。
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.database import get_db
from api.dependencies import require_permission
from services.data_scope_service import DataScopeService
from services import alert_service
from models.alert_record import AlertRecord
from models.app_service import AppService
from schemas.common import ResponseModel

router = APIRouter()

MAX_PAGE_SIZE = 100


class ConfirmRequest(BaseModel):
    note: Optional[str] = None


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _scoped_query(db: Session, user):
    """按当前用户可见项目范围过滤告警（复用 DataScope）。"""
    query = db.query(AlertRecord)
    visible_ids = DataScopeService.get_user_project_ids(db, user)
    if visible_ids is None:
        return query
    if not visible_ids:
        # 无可见项目：返回空集（不得放宽）
        return query.filter(AlertRecord.id < 0)
    return query.filter(AlertRecord.project_id.in_(visible_ids))


def _assert_alert_access(db: Session, user, record: AlertRecord) -> None:
    """单条告警越权校验，失败返回 404（不泄漏存在性）。"""
    if record is None or record.project_id is None:
        raise HTTPException(status_code=404, detail="告警不存在")
    if not DataScopeService.can_access_project(db, user, record.project_id):
        raise HTTPException(status_code=404, detail="告警不存在")


def _service_name_map(db: Session, service_ids: List[int]) -> dict:
    if not service_ids:
        return {}
    rows = db.query(AppService.id, AppService.func_desc).filter(AppService.id.in_(service_ids)).all()
    return {sid: name for sid, name in rows}


def _serialize(rec: AlertRecord, name_map: dict) -> dict:
    return {
        "id": rec.id,
        "source": rec.source,
        "alert_type": rec.alert_type,
        "severity": rec.severity,
        "status": rec.status,
        "service_id": rec.service_id,
        "service_name": name_map.get(rec.service_id) or (f"服务#{rec.service_id}" if rec.service_id else "-"),
        "project_id": rec.project_id,
        "subsystem_id": rec.subsystem_id,
        "agent_uuid": rec.agent_uuid,
        "ip": rec.ip,
        "title": rec.title,
        "content": rec.content,
        "first_seen_at": rec.first_seen_at,
        "last_seen_at": rec.last_seen_at,
        "confirmed_by_name": rec.confirmed_by_name,
        "confirmed_at": rec.confirmed_at,
        "handle_note": rec.handle_note,
        "recovered_at": rec.recovered_at,
    }


@router.get("/alerts/records", response_model=ResponseModel)
async def list_alert_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    project_id: Optional[int] = Query(None),
    subsystem_id: Optional[int] = Query(None),
    service_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user=Depends(require_permission("service:view")),
):
    query = _scoped_query(db, user)

    if status:
        query = query.filter(AlertRecord.status == status)
    if severity:
        query = query.filter(AlertRecord.severity == severity)
    if alert_type:
        query = query.filter(AlertRecord.alert_type == alert_type)
    if project_id is not None:
        query = query.filter(AlertRecord.project_id == project_id)
    if subsystem_id is not None:
        query = query.filter(AlertRecord.subsystem_id == subsystem_id)
    if service_id is not None:
        query = query.filter(AlertRecord.service_id == service_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (AlertRecord.title.like(like))
            | (AlertRecord.content.like(like))
            | (AlertRecord.ip.like(like))
        )
    st = _parse_dt(start_time)
    et = _parse_dt(end_time)
    if st:
        query = query.filter(AlertRecord.first_seen_at >= st)
    if et:
        query = query.filter(AlertRecord.first_seen_at <= et)

    total = query.count()
    rows = (
        query.order_by(AlertRecord.first_seen_at.desc(), AlertRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    name_map = _service_name_map(db, [r.service_id for r in rows if r.service_id])
    return ResponseModel(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize(r, name_map) for r in rows],
    })


@router.get("/alerts/records/stats", response_model=ResponseModel)
async def alert_stats(
    db: Session = Depends(get_db),
    user=Depends(require_permission("service:view")),
):
    base = _scoped_query(db, user)
    status_rows = base.with_entities(AlertRecord.status, func.count(AlertRecord.id)).group_by(AlertRecord.status).all()
    by_status = {s: int(c) for s, c in status_rows}

    open_query = _scoped_query(db, user).filter(AlertRecord.status != "RECOVERED")
    sev_rows = open_query.with_entities(AlertRecord.severity, func.count(AlertRecord.id)).group_by(AlertRecord.severity).all()
    open_by_severity = {s: int(c) for s, c in sev_rows}

    return ResponseModel(data={
        "total": sum(by_status.values()),
        "by_status": by_status,
        "open_by_severity": open_by_severity,
        "open_total": sum(open_by_severity.values()),
    })


@router.get("/alerts/records/{alert_id}", response_model=ResponseModel)
async def get_alert_record(
    alert_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permission("service:view")),
):
    record = alert_service.get_alert(db, alert_id)
    _assert_alert_access(db, user, record)
    name_map = _service_name_map(db, [record.service_id] if record.service_id else [])
    return ResponseModel(data=_serialize(record, name_map))


@router.post("/alerts/records/{alert_id}/confirm", response_model=ResponseModel)
async def confirm_alert_record(
    alert_id: int,
    payload: ConfirmRequest,
    db: Session = Depends(get_db),
    user=Depends(require_permission("service_operate")),
):
    record = alert_service.get_alert(db, alert_id)
    _assert_alert_access(db, user, record)
    ok = alert_service.confirm_alert(db, record, user, payload.note)
    if not ok:
        return ResponseModel(code=1, message="告警已恢复，无法确认", data=None)
    name_map = _service_name_map(db, [record.service_id] if record.service_id else [])
    return ResponseModel(data=_serialize(record, name_map))
