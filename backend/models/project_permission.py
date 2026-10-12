from sqlalchemy import Column, BIGINT, ForeignKey, DATETIME, Enum, Index, Boolean
from sqlalchemy.sql import func
from core.database import Base


class ProjectPermission(Base):
    __tablename__ = "project_permissions"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    project_id = Column(BIGINT, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="项目ID")
    target_type = Column(Enum("Organization", "Department", "User"), nullable=False, comment="授权目标类型")
    target_id = Column(BIGINT, nullable=False, comment="授权目标ID")
    permission = Column(Enum("READ", "EDIT", "MANAGE"), nullable=False, default="READ", comment="权限等级：READ-只读，EDIT/MANAGE-读写")
    created_by = Column(BIGINT, nullable=False, comment="创建人ID")
    created_time = Column(DATETIME, server_default=func.now(), comment="创建时间")

    # 高风险能力独立授权（不随"读写"自动开放，默认关闭）
    allow_webshell = Column(Boolean, nullable=False, default=False, server_default="0", comment="允许 WebShell 远程终端")
    allow_root = Column(Boolean, nullable=False, default=False, server_default="0", comment="允许 Root 登录")
    allow_sftp = Column(Boolean, nullable=False, default=False, server_default="0", comment="允许 SFTP 文件操作")
    allow_service_delete = Column(Boolean, nullable=False, default=False, server_default="0", comment="允许服务删除")
    allow_service_deploy = Column(Boolean, nullable=False, default=False, server_default="0", comment="允许服务发布")
    allow_backup = Column(Boolean, nullable=False, default=False, server_default="0", comment="允许备份/恢复")

    __table_args__ = (
        Index("idx_pp_project", "project_id"),
        Index("idx_pp_target", "target_type", "target_id"),
        Index("idx_pp_permission", "permission"),
        {"comment": "项目共享授权表"},
    )


# 高风险能力 → ProjectPermission 独立授权字段
HIGH_RISK_FLAG_BY_CAPABILITY = {
    "webshell": "allow_webshell",
    "root": "allow_root",
    "sftp": "allow_sftp",
    "delete": "allow_service_delete",
    "deploy": "allow_service_deploy",
    "backup": "allow_backup",
}


WRITE_PERMISSION_LEVELS = ("EDIT", "MANAGE")


def is_write_permission(permission: str) -> bool:
    """共享级别是否为"读写"：EDIT/MANAGE 均视为读写，READ 为只读"""
    return permission in WRITE_PERMISSION_LEVELS
