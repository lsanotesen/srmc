from sqlalchemy import Column, BIGINT, ForeignKey, DATETIME, Enum, Index
from sqlalchemy.sql import func
from core.database import Base


class ProjectPermission(Base):
    __tablename__ = "project_permissions"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    project_id = Column(BIGINT, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="项目ID")
    target_type = Column(Enum("Organization", "Department", "User"), nullable=False, comment="授权目标类型")
    target_id = Column(BIGINT, nullable=False, comment="授权目标ID")
    permission = Column(Enum("READ", "EDIT", "MANAGE"), nullable=False, default="READ", comment="权限等级")
    created_by = Column(BIGINT, nullable=False, comment="创建人ID")
    created_time = Column(DATETIME, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        Index("idx_pp_project", "project_id"),
        Index("idx_pp_target", "target_type", "target_id"),
        Index("idx_pp_permission", "permission"),
        {"comment": "项目共享授权表"},
    )
