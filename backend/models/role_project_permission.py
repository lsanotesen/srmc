from sqlalchemy import Column, BIGINT, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import ENUM
from sqlalchemy.sql import func
from core.database import Base


class RoleProjectPermission(Base):
    __tablename__ = "role_project_permissions"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    role_id = Column(BIGINT, nullable=False, comment="角色ID")
    project_id = Column(BIGINT, nullable=False, comment="项目ID")
    permission_level = Column(
        ENUM("READ", "EDIT", "MANAGE"),
        nullable=False,
        default="READ",
        comment="权限级别: READ-只读, EDIT-编辑, MANAGE-管理",
    )
    created_at = Column(BIGINT, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("role_id", "project_id", name="uk_role_project"),
        Index("idx_rpp_role", "role_id"),
        Index("idx_rpp_project", "project_id"),
        {"comment": "角色项目权限关联表"},
    )
