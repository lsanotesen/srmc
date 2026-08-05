from sqlalchemy import Column, BIGINT, VARCHAR, TEXT, DATETIME, ForeignKey, Index, Integer
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    organization_id = Column(BIGINT, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, comment="所属组织ID")
    parent_id = Column(BIGINT, ForeignKey("departments.id", ondelete="CASCADE"), comment="父部门ID, NULL表示根部门")
    name = Column(VARCHAR(100), nullable=False, comment="部门名称")
    code = Column(VARCHAR(50), nullable=False, comment="部门编码")
    leader_id = Column(BIGINT, comment="部门负责人用户ID")
    description = Column(TEXT, comment="描述")
    status = Column(TINYINT(1), nullable=False, default=1, comment="状态: 1-启用, 0-禁用")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DATETIME, server_default=func.now())
    updated_at = Column(DATETIME, server_default=func.now(), onupdate=func.now())

    children = relationship("Department", backref="parent", remote_side=[id], cascade="all")

    __table_args__ = (
        Index("idx_dept_org", "organization_id"),
        Index("idx_dept_parent", "parent_id"),
        Index("idx_dept_code", "code"),
        Index("idx_dept_status", "status"),
        {"comment": "部门表"},
    )
