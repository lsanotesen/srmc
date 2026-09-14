"""迁移：扩展 audit_logs.action 枚举，加入 Agent 安装包/批量装机操作"""
from sqlalchemy import create_engine, text
from core.config import settings

engine = create_engine(settings.DATABASE_URL)

# 完整枚举（含新增项），与 models/audit_log.py 保持一致
ENUM_VALUES = [
    "START", "STOP", "RESTART", "SHELL", "LOG", "SQL", "IMPORT", "EXPORT",
    "LOGIN", "CREATE", "UPDATE", "DELETE", "PROJECT_CREATE", "PROJECT_UPDATE",
    "PROJECT_DELETE", "PROJECT_IMPORT", "CREATE_PROJECT", "DELETE_PROJECT",
    "SERVICE_CREATE", "SERVICE_UPDATE", "SERVICE_DELETE", "SERVICE_START",
    "SERVICE_STOP", "SERVICE_RESTART", "SERVICE_AUTOSTART", "SUBSYSTEM_CREATE",
    "SUBSYSTEM_UPDATE", "SUBSYSTEM_DELETE", "SERVICE_GROUP_CREATE",
    "SERVICE_GROUP_UPDATE", "SERVICE_GROUP_DELETE", "SERVICE_GROUP_CLEANUP",
    "SERVICE_IMPORT",
    "AGENT_CONTROL", "AGENT_BATCH_CONTROL", "ROLE_CREATE", "ROLE_UPDATE",
    "ROLE_DELETE", "PERMISSION_GRANT", "PERMISSION_REVOKE", "PROJECT_SHARE",
    "PROJECT_SHARE_REMOVE", "ORG_CREATE", "ORG_UPDATE", "ORG_DELETE",
    "DEPT_CREATE", "DEPT_UPDATE", "DEPT_DELETE",
    "PROJECT_MEMBER_BATCH_ADD",
    "BACKUP_CREATE", "BACKUP_RESTORE", "IMPORT_REVERT",
    "AGENT_UPDATE", "AGENT_UPDATE_CANCEL",
    "AGENT_PACKAGE_UPLOAD", "AGENT_PACKAGE_DELETE",
    "AGENT_DEPLOY", "AGENT_DEPLOY_CANCEL",
]

ddl = "ALTER TABLE audit_logs MODIFY COLUMN action ENUM(%s) NOT NULL" % ",".join(
    "'%s'" % v for v in ENUM_VALUES
)

with engine.connect() as conn:
    # 幂等：检查新枚举是否已存在
    row = conn.execute(text(
        "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'audit_logs' AND COLUMN_NAME = 'action'"
    )).fetchone()
    col_type = row[0] if row else ""
    if "AGENT_DEPLOY_CANCEL" in col_type:
        print("audit_logs.action enum already extended")
    else:
        conn.execute(text(ddl))
        conn.commit()
        print("Extended audit_logs.action enum")

print("Migration 0015 completed")
