from sqlalchemy.orm import Session
from models.audit_log import AuditLog
from datetime import datetime
from core.config import settings
from apscheduler.schedulers.background import BackgroundScheduler
import os

def log_audit(db: Session, user_id: int, username: str, action: str, 
              service_id: int = None, service_code: str = None,
              server_id: int = None, ip: str = None,
              result: str = "success", output: str = None, duration: int = None):
    if output and len(output) > 2000:
        output = output[:2000] + "..."
    
    audit_log = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        service_id=service_id,
        service_code=service_code,
        server_id=server_id,
        ip=ip,
        result=result,
        output=output,
        duration=duration
    )
    db.add(audit_log)
    db.commit()

def clean_expired_audit_logs(db: Session):
    expire_date = datetime.now() - timedelta(days=settings.AUDIT_LOG_RETENTION_DAYS)
    db.query(AuditLog).filter(AuditLog.created_at < expire_date).delete()
    db.commit()

def start_audit_cleanup_job(db):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        clean_expired_audit_logs,
        'cron',
        hour=0,
        minute=0,
        args=[db]
    )
    scheduler.start()
