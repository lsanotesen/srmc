from sqlalchemy import Column, BIGINT, VARCHAR, TEXT, DATETIME, ForeignKey, Index
from sqlalchemy.dialects.mysql import ENUM
from core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    user_id = Column(BIGINT, ForeignKey("users.id"))
    username = Column(VARCHAR(64), nullable=False)
    action = Column(
        ENUM(
            "START", "STOP", "RESTART", "SHELL", "LOG", "SQL", "IMPORT", "EXPORT",
            "LOGIN", "CREATE", "UPDATE", "DELETE", "PROJECT_CREATE", "PROJECT_UPDATE",
            "PROJECT_DELETE", "PROJECT_IMPORT", "CREATE_PROJECT", "DELETE_PROJECT",
            "SERVICE_CREATE", "SERVICE_UPDATE", "SERVICE_DELETE", "SERVICE_START",
            "SERVICE_STOP", "SERVICE_RESTART", "SERVICE_AUTOSTART", "SUBSYSTEM_CREATE",
            "SUBSYSTEM_UPDATE", "SUBSYSTEM_DELETE", "SERVICE_GROUP_CREATE",
            "SERVICE_GROUP_UPDATE", "SERVICE_GROUP_DELETE", "SERVICE_IMPORT",
            "AGENT_CONTROL", "AGENT_BATCH_CONTROL", "ROLE_CREATE", "ROLE_UPDATE",
            "ROLE_DELETE", "PERMISSION_GRANT", "PERMISSION_REVOKE", "PROJECT_SHARE",
            "PROJECT_SHARE_REMOVE", "ORG_CREATE", "ORG_UPDATE", "ORG_DELETE",
            "DEPT_CREATE", "DEPT_UPDATE", "DEPT_DELETE",
            "PROJECT_MEMBER_BATCH_ADD"
        ),
        nullable=False,
    )
    service_id = Column(BIGINT, ForeignKey("services.id"))
    service_code = Column(VARCHAR(64))
    server_id = Column(BIGINT, ForeignKey("servers.id"))
    ip = Column(VARCHAR(45))
    organization_id = Column(BIGINT, comment="组织ID")
    department_id = Column(BIGINT, comment="部门ID")
    request_url = Column(VARCHAR(500), comment="请求URL")
    request_params = Column(TEXT, comment="请求参数")
    user_agent = Column(VARCHAR(500), comment="浏览器UA")
    result = Column(ENUM("success", "failed", "partial"), nullable=False)
    output = Column(TEXT)
    duration = Column(BIGINT)
    created_at = Column(DATETIME, server_default="CURRENT_TIMESTAMP")

    __table_args__ = (
        Index("idx_audit_org", "organization_id"),
        Index("idx_audit_dept", "department_id"),
    )
