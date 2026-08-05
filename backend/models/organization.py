from sqlalchemy import Column, BIGINT, VARCHAR, TEXT, DATETIME, Index
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.sql import func
from core.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    name = Column(VARCHAR(100), nullable=False, comment="组织名称")
    code = Column(VARCHAR(50), nullable=False, unique=True, comment="组织编码")
    logo = Column(VARCHAR(500), comment="Logo URL")
    description = Column(TEXT, comment="描述")
    status = Column(TINYINT(1), nullable=False, default=1, comment="状态: 1-启用, 0-禁用")
    created_at = Column(DATETIME, server_default=func.now())
    updated_at = Column(DATETIME, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_org_code", "code"),
        Index("idx_org_status", "status"),
        {"comment": "组织机构表"},
    )
