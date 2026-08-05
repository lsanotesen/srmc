from sqlalchemy import Column, BIGINT, ForeignKey, DATETIME, Enum, Index
from sqlalchemy.sql import func
from core.database import Base


class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    project_id = Column(BIGINT, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="项目ID")
    user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    role = Column(Enum("Owner", "Manager", "Developer", "Operator", "Viewer"), nullable=False, default="Viewer", comment="项目角色")
    join_time = Column(DATETIME, server_default=func.now(), comment="加入时间")
    created_at = Column(DATETIME, server_default=func.now())

    __table_args__ = (
        Index("uk_project_user", "project_id", "user_id", unique=True),
        Index("idx_pm_project", "project_id"),
        Index("idx_pm_user", "user_id"),
        Index("idx_pm_role", "role"),
        {"comment": "项目成员表"},
    )
