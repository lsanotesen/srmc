from sqlalchemy import Column, BIGINT, VARCHAR, TEXT, ForeignKey, DATETIME, Index
from sqlalchemy.sql import func
from core.database import Base


class ResourceGroup(Base):
    __tablename__ = "resource_groups"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    project_id = Column(BIGINT, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="项目ID")
    name = Column(VARCHAR(100), nullable=False, comment="资源组名称")
    description = Column(TEXT, comment="描述")
    created_at = Column(DATETIME, server_default=func.now())
    updated_at = Column(DATETIME, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_rg_project", "project_id"),
        {"comment": "资源组表"},
    )
