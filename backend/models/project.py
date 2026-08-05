from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, comment="项目名称")
    code = Column(String(50), comment="项目编码")
    description = Column(Text, comment="项目描述")
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), comment="所属组织ID")
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), comment="所属部门ID")
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), comment="创建人ID")
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), comment="负责人ID")
    visibility = Column(String(20), nullable=False, default="DEPARTMENT", comment="可见性: DEPARTMENT/AUTHORIZED/PUBLIC")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    subsystems = relationship("Subsystem", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_project_org", "organization_id"),
        Index("idx_project_dept", "department_id"),
        Index("idx_project_visibility", "visibility"),
    )
