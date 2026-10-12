"""数据库备份 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import os

from core.database import get_db
from schemas.common import ResponseModel
from api.dependencies import require_permission
from models.db_backup import DbBackupConfig, DbBackupRecord
from services import backup_service

router = APIRouter()


class BackupConfigIn(BaseModel):
    enabled: Optional[int] = None
    schedule_type: Optional[str] = None   # daily | weekly
    schedule_time: Optional[str] = None   # "HH:MM"
    week_day: Optional[int] = None        # 0-6 周一~周日
    retention_count: Optional[int] = None


class RestoreIn(BaseModel):
    confirm_filename: str


@router.get("/backup/config", response_model=ResponseModel)
async def get_backup_config(
    db: Session = Depends(get_db),
    user=Depends(require_permission("backup:view"))
):
    backup_service.ensure_default_config()
    cfg = db.query(DbBackupConfig).first()
    return ResponseModel(data={
        'id': cfg.id,
        'enabled': bool(cfg.enabled),
        'schedule_type': cfg.schedule_type,
        'schedule_time': cfg.schedule_time.strftime('%H:%M') if cfg.schedule_time else '02:00',
        'week_day': cfg.week_day or 1,
        'retention_count': cfg.retention_count or 10,
        'last_run_at': cfg.last_run_at.strftime('%Y-%m-%d %H:%M:%S') if cfg.last_run_at else None,
        'updated_at': cfg.updated_at.strftime('%Y-%m-%d %H:%M:%S') if cfg.updated_at else None,
    })


@router.put("/backup/config", response_model=ResponseModel)
async def update_backup_config(
    body: BackupConfigIn,
    db: Session = Depends(get_db),
    user=Depends(require_permission("backup:manage"))
):
    backup_service.ensure_default_config()
    cfg = db.query(DbBackupConfig).first()

    from datetime import datetime, time as dtime

    if body.enabled is not None:
        cfg.enabled = 1 if body.enabled else 0
    if body.schedule_type in ('daily', 'weekly'):
        cfg.schedule_type = body.schedule_type
    if body.schedule_time:
        try:
            hh, mm = body.schedule_time.split(':')
            hh, mm = int(hh), int(mm)
            assert 0 <= hh <= 23 and 0 <= mm <= 59
            cfg.schedule_time = dtime(hour=hh, minute=mm)
        except Exception:
            raise HTTPException(status_code=422, detail="时间格式无效，应为 HH:MM")
    if body.week_day is not None:
        if not (0 <= int(body.week_day) <= 6):
            raise HTTPException(status_code=422, detail="星期值应为 0(周一)~6(周日)")
        cfg.week_day = int(body.week_day)
    if body.retention_count is not None:
        if not (1 <= int(body.retention_count) <= 100):
            raise HTTPException(status_code=422, detail="保留份数应为 1~100")
        cfg.retention_count = int(body.retention_count)

    db.commit()
    # 动态重排定时任务
    backup_service.apply_schedule_from_config()
    return ResponseModel(data={'id': cfg.id}, message='配置已保存')


@router.get("/backup/records", response_model=ResponseModel)
async def list_backup_records(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(require_permission("backup:view"))
):
    from sqlalchemy import func
    total = db.query(func.count(DbBackupRecord.id)).scalar()
    rows = (db.query(DbBackupRecord)
            .order_by(DbBackupRecord.created_at.desc())
            .offset((page - 1) * size).limit(size).all())
    items = [{
        'id': r.id,
        'filename': r.filename,
        'file_size': r.file_size,
        'backup_type': r.backup_type,
        'status': r.status,
        'table_count': r.table_count,
        'duration_ms': r.duration_ms,
        'error_message': r.error_message,
        'created_by': r.created_by,
        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else None,
    } for r in rows]
    return ResponseModel(data={'items': items, 'total': total, 'page': page, 'size': size})


@router.post("/backup/run", response_model=ResponseModel)
async def run_manual_backup(
    db: Session = Depends(get_db),
    user=Depends(require_permission("backup:manage"))
):
    try:
        rec = backup_service.run_backup(
            backup_type='manual', created_by=user.username)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"备份失败: {str(e)[:300]}")

    return ResponseModel(data={
        'id': rec.id,
        'filename': rec.filename,
        'file_size': rec.file_size,
        'duration_ms': rec.duration_ms,
        'table_count': rec.table_count,
    }, message=f"备份完成: {rec.filename}")


@router.get("/backup/{record_id}/download")
async def download_backup(
    record_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permission("backup:manage"))
):
    rec = db.query(DbBackupRecord).filter(DbBackupRecord.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    # 从记录读取路径，防止前端传路径造成目录穿越
    path = rec.file_path
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="备份文件已丢失")
    return FileResponse(path, filename=rec.filename, media_type='application/gzip')


@router.delete("/backup/records/{record_id}", response_model=ResponseModel)
async def delete_backup_record(
    record_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permission("backup:manage"))
):
    try:
        backup_service.delete_record(record_id)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ResponseModel(data=None, message='已删除')


@router.post("/backup/{record_id}/restore", response_model=ResponseModel)
async def restore_backup(
    record_id: int,
    body: RestoreIn,
    db: Session = Depends(get_db),
    user=Depends(require_permission("backup:manage"))
):
    # 鉴权 SELECT 会在请求 session 上开启事务并保持到响应结束，
    # 长期持有 metadata lock 会阻塞恢复的 DDL，先显式提交释放
    db.commit()
    try:
        result = backup_service.restore_from_record(record_id, body.confirm_filename)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ResponseModel(data=result, message=f"恢复成功，来源 {result['restored_from']}")
