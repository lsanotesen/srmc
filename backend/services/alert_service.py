"""服务状态告警业务逻辑（告警中心基础版）

设计原则：
- 数据库为唯一真相源。去重、恢复、状态迁移全部以 DB 查询结果为准。
- dedup_key 不设唯一约束，同一服务每个异常周期一行，历史可追溯；
  活动告警去重由「查询 dedup_key 相同且 status<>'RECOVERED'」保证。
- 状态机：ACTIVE → CONFIRMED（用户确认）；ACTIVE/CONFIRMED → RECOVERED（真实业务状态转健康）；
  RECOVERED 为终态不可回退。持续异常只更新 last_seen_at，不覆盖 status（确认不被覆盖）。
- 恢复只由真实业务状态触发；UNKNOWN / 无数据（Agent 离线、Redis 过期）不触发恢复，避免假恢复。
- 心跳按 Agent 批量评估：一次查询该 Agent 全部服务的未恢复告警，避免逐服务查库。
"""
from datetime import datetime
from typing import Optional, List, Tuple, Dict

from sqlalchemy.orm import Session

from models.alert_record import (
    AlertRecord,
    SOURCE_AGENT_STATUS,
    TYPE_SERVICE_STOPPED,
    TYPE_SERVICE_FAILED,
    TYPE_SERVICE_PARTIAL,
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
    STATUS_ACTIVE,
    STATUS_CONFIRMED,
    STATUS_RECOVERED,
)
from models.app_service import AppService
from models.project import Project
import services.container_status_service as css

# 业务异常状态 -> (告警类型, 级别)。健康状态见 container_status_service.HEALTHY_STATUSES
ABNORMAL_MAP = {
    css.ST_STOPPED: (TYPE_SERVICE_STOPPED, SEVERITY_CRITICAL),
    css.ST_FAILED: (TYPE_SERVICE_FAILED, SEVERITY_CRITICAL),
    css.ST_PARTIAL: (TYPE_SERVICE_PARTIAL, SEVERITY_WARNING),
}


def _now() -> datetime:
    return datetime.now()


def dedup_key_for(service_id) -> str:
    return f"SERVICE_STATUS:{service_id}"


def _title_for(alert_type: str) -> str:
    return {
        TYPE_SERVICE_STOPPED: "服务已停止",
        TYPE_SERVICE_FAILED: "服务运行异常",
        TYPE_SERVICE_PARTIAL: "服务部分运行",
    }.get(alert_type, "服务状态异常")


def _content_for(svc: Optional[AppService], status: str) -> str:
    name = getattr(svc, "func_desc", None) or (f"服务#{svc.id}" if svc else "")
    ip = getattr(svc, "ip", None) or "-"
    return f"服务「{name}」业务状态为 {status}（IP: {ip}）。"


def evaluate_heartbeat_statuses(
    db: Session,
    statuses: List[Tuple[int, str]],
    agent_uuid: Optional[str] = None,
):
    """根据一次心跳上报的多个服务业务状态，维护告警记录。

    statuses: [(service_id, new_status), ...]
    返回本次处理摘要（便于排查），不影响主流程。
    """
    items = [(int(sid), st) for sid, st in statuses if sid and st]
    if not items:
        return {"created": 0, "updated": 0, "recovered": 0}

    # 一次性取出这些服务的未恢复告警（DB 为唯一真相源）
    keys = [dedup_key_for(sid) for sid, _ in items]
    open_rows = (
        db.query(AlertRecord)
        .filter(AlertRecord.dedup_key.in_(keys), AlertRecord.status != STATUS_RECOVERED)
        .order_by(AlertRecord.id.asc())
        .all()
    )
    # 每个 dedup_key 取最新一条未恢复记录（正常每 key 至多一条）
    open_map: Dict[str, AlertRecord] = {}
    for row in open_rows:
        open_map[row.dedup_key] = row

    created = updated = recovered = 0
    now = _now()

    try:
        for service_id, new_status in items:
            key = dedup_key_for(service_id)
            record = open_map.get(key)

            if new_status in ABNORMAL_MAP:
                alert_type, severity = ABNORMAL_MAP[new_status]
                if record:
                    # 持续异常：只刷新最近发生时间与可能变化的展示字段；
                    # 不新增、不改 status（CONFIRMED 不被覆盖）、不改 first_seen_at。
                    record.last_seen_at = now
                    record.alert_type = alert_type
                    record.severity = severity
                    record.title = _title_for(alert_type)
                    if agent_uuid:
                        record.agent_uuid = agent_uuid
                    record.updated_at = now
                    updated += 1
                else:
                    rec = _create_alert(db, service_id, alert_type, severity, agent_uuid, now)
                    open_map[key] = rec
                    created += 1

            elif css.is_healthy(new_status):
                # 恢复只由真实业务状态触发；无未恢复记录则无需处理
                if record:
                    record.status = STATUS_RECOVERED
                    record.recovered_at = now
                    record.updated_at = now
                    open_map.pop(key, None)
                    recovered += 1
            # 其余（UNKNOWN 等无数据/未知）：既不新建也不恢复，避免假恢复

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Alert] evaluate heartbeat failed: {e}")
        return {"created": 0, "updated": 0, "recovered": 0, "error": str(e)}

    return {"created": created, "updated": updated, "recovered": recovered}


def _create_alert(
    db: Session,
    service_id: int,
    alert_type: str,
    severity: str,
    agent_uuid: Optional[str],
    now: datetime,
) -> AlertRecord:
    """新建活动告警（首次异常，或恢复后再次异常）。"""
    svc = db.query(AppService).filter(AppService.id == service_id).first()
    project_id = getattr(svc, "project_id", None) if svc else None
    subsystem_id = getattr(svc, "subsystem_id", None) if svc else None

    org_id = dept_id = None
    if project_id:
        proj = db.query(Project).filter(Project.id == project_id).first()
        if proj:
            org_id = proj.organization_id
            dept_id = proj.department_id

    rec = AlertRecord(
        dedup_key=dedup_key_for(service_id),
        source=SOURCE_AGENT_STATUS,
        alert_type=alert_type,
        severity=severity,
        service_id=service_id,
        project_id=project_id,
        subsystem_id=subsystem_id,
        organization_id=org_id,
        department_id=dept_id,
        agent_uuid=agent_uuid or (getattr(svc, "agent_uuid", None) if svc else None),
        ip=(getattr(svc, "ip", None) if svc else None),
        title=_title_for(alert_type),
        content=_content_for(svc, _status_text_for(alert_type)),
        status=STATUS_ACTIVE,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(rec)
    return rec


def _status_text_for(alert_type: str) -> str:
    return {
        TYPE_SERVICE_STOPPED: css.ST_STOPPED,
        TYPE_SERVICE_FAILED: css.ST_FAILED,
        TYPE_SERVICE_PARTIAL: css.ST_PARTIAL,
    }.get(alert_type, css.ST_UNKNOWN)


# ---------------- 人工操作：确认 / 恢复 ----------------

def get_alert(db: Session, alert_id: int) -> Optional[AlertRecord]:
    return db.query(AlertRecord).filter(AlertRecord.id == alert_id).first()


def confirm_alert(db: Session, record: AlertRecord, user, note: Optional[str] = None) -> bool:
    """确认告警。仅 ACTIVE → CONFIRMED；CONFIRMED 幂等；RECOVERED 不允许（返回 False）。"""
    if record.status == STATUS_RECOVERED:
        return False
    if record.status != STATUS_CONFIRMED:
        record.status = STATUS_CONFIRMED
        record.confirmed_by = getattr(user, "id", None)
        record.confirmed_by_name = getattr(user, "username", None)
        record.confirmed_at = _now()
    if note is not None:
        record.handle_note = note
    record.updated_at = _now()
    db.commit()
    return True
