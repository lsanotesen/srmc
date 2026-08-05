from sqlalchemy import Column, BIGINT, VARCHAR, DATETIME, Index, UniqueConstraint
from sqlalchemy.sql import func
from core.database import Base


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    resource = Column(VARCHAR(50), nullable=False, comment="资源类型: project, service, docker, image, webshell, host, config, log, script, file")
    action = Column(VARCHAR(50), nullable=False, comment="操作: view, add, edit, delete, start, stop, restart, exec, remove, upload, download, login, run, reboot, share")
    name = Column(VARCHAR(100), nullable=False, comment="权限名称")
    description = Column(VARCHAR(255), comment="权限描述")
    created_at = Column(DATETIME, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("resource", "action", name="uk_resource_action"),
        Index("idx_perm_resource", "resource"),
        {"comment": "权限定义表"},
    )
