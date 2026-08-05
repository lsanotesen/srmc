from sqlalchemy.orm import Session
from models.audit_log import AuditLog
from models.user import User
from models.project import Project
from models.department import Department
from models.organization import Organization
from datetime import datetime, timedelta
from core.config import settings
from apscheduler.schedulers.background import BackgroundScheduler
import json
import asyncio


def log_audit(
    db: Session,
    user_id: int,
    username: str,
    action: str,
    service_id: int = None,
    service_code: str = None,
    server_id: int = None,
    ip: str = None,
    result: str = "success",
    output: str = None,
    duration: int = None,
    request_url: str = None,
    request_params: str = None,
    user_agent: str = None,
    project_id: int = None,
):
    """
    增强版审计日志记录
    支持组织、部门、项目关联，请求URL/参数记录
    """
    if output and len(output) > 2000:
        output = output[:2000] + "..."

    org_id = None
    dept_id = None

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        org_id = user.organization_id
        dept_id = user.department_id

    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            org_id = org_id or project.organization_id
            dept_id = dept_id or project.department_id

    if request_params and len(request_params) > 2000:
        request_params = request_params[:2000] + "..."

    audit_log = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        service_id=service_id,
        service_code=service_code,
        server_id=server_id,
        ip=ip,
        organization_id=org_id,
        department_id=dept_id,
        request_url=request_url,
        request_params=request_params,
        user_agent=user_agent,
        result=result,
        output=output,
        duration=duration,
    )
    db.add(audit_log)
    db.commit()


def log_audit_async(
    user_id: int,
    username: str,
    action: str,
    **kwargs,
):
    """异步记录审计日志（不阻塞主业务流程）"""
    from core.database import SessionLocal

    def _do_log():
        db = SessionLocal()
        try:
            log_audit(db, user_id, username, action, **kwargs)
        except Exception as e:
            print(f"[Audit] Async logging failed: {e}")
        finally:
            db.close()

    try:
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _do_log)
    except RuntimeError:
        _do_log()


def clean_expired_audit_logs(db: Session):
    expire_date = datetime.now() - timedelta(days=settings.AUDIT_LOG_RETENTION_DAYS)
    db.query(AuditLog).filter(AuditLog.created_at < expire_date).delete()
    db.commit()


def start_audit_cleanup_job(db: Session):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        clean_expired_audit_logs,
        "cron",
        hour=0,
        minute=0,
        args=[db],
    )
    scheduler.start()
