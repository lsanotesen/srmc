"""告警记录：服务业务状态异常告警（基础版）

设计要点：
- 唯一真相源为数据库。dedup_key 不设唯一约束，同一服务在多个异常周期会产生多行历史：
  活动告警去重由应用层「查询 dedup_key 相同且 status<>'RECOVERED'」保证；
  恢复后再次异常时无未恢复记录，自然新建新行，历史完整可追溯。
- 状态机：ACTIVE → CONFIRMED（用户确认）；ACTIVE/CONFIRMED → RECOVERED（真实业务状态转健康）；
  RECOVERED 为终态不可回退，持续异常心跳只更新 last_seen_at，不覆盖 status。
"""
from sqlalchemy import Column, BIGINT, VARCHAR, TEXT, DATETIME, Index
from core.database import Base

# 告警来源
SOURCE_AGENT_STATUS = "AGENT_STATUS"

# 告警类型
TYPE_SERVICE_STOPPED = "SERVICE_STOPPED"
TYPE_SERVICE_FAILED = "SERVICE_FAILED"
TYPE_SERVICE_PARTIAL = "SERVICE_PARTIAL"

# 告警级别
SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"

# 告警状态机
STATUS_ACTIVE = "ACTIVE"
STATUS_CONFIRMED = "CONFIRMED"
STATUS_RECOVERED = "RECOVERED"


class AlertRecord(Base):
    __tablename__ = 'alert_records'

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    # 去重键：SERVICE_STATUS:{service_id}。故意不设唯一约束（见模块说明）
    dedup_key = Column(VARCHAR(128), nullable=False, comment='去重键')
    source = Column(VARCHAR(32), nullable=False, default=SOURCE_AGENT_STATUS, comment='告警来源')
    alert_type = Column(VARCHAR(32), nullable=False, comment='告警类型')
    severity = Column(VARCHAR(16), nullable=False, comment='级别: critical/warning')

    service_id = Column(BIGINT, comment='服务ID(app_services.id)')
    project_id = Column(BIGINT, comment='项目ID')
    subsystem_id = Column(BIGINT, comment='子系统ID')
    # 冗余自项目，供 DataScope 快速过滤（与 audit_logs 一致）
    organization_id = Column(BIGINT, comment='组织ID')
    department_id = Column(BIGINT, comment='部门ID')

    agent_uuid = Column(VARCHAR(64), comment='来源Agent UUID')
    ip = Column(VARCHAR(45), comment='服务IP')
    title = Column(VARCHAR(255), comment='告警标题')
    content = Column(TEXT, comment='告警详情')

    status = Column(VARCHAR(16), nullable=False, default=STATUS_ACTIVE, comment='ACTIVE/CONFIRMED/RECOVERED')
    first_seen_at = Column(DATETIME, comment='首次发生时间')
    last_seen_at = Column(DATETIME, comment='最近发生时间')

    confirmed_by = Column(BIGINT, comment='确认人ID')
    confirmed_by_name = Column(VARCHAR(64), comment='确认人用户名')
    confirmed_at = Column(DATETIME, comment='确认时间')
    handle_note = Column(TEXT, comment='处理说明')

    recovered_at = Column(DATETIME, comment='恢复时间')
    created_at = Column(DATETIME)
    updated_at = Column(DATETIME)

    __table_args__ = (
        # 非唯一索引：既支持去重查询，又允许同 key 多行历史
        Index('idx_alert_dedup', 'dedup_key'),
        Index('idx_alert_dedup_status', 'dedup_key', 'status'),
        Index('idx_alert_status', 'status'),
        Index('idx_alert_project', 'project_id'),
        Index('idx_alert_service', 'service_id'),
        Index('idx_alert_org', 'organization_id'),
        Index('idx_alert_dept', 'department_id'),
        Index('idx_alert_first_seen', 'first_seen_at'),
        {'comment': '服务状态告警记录'},
    )
