from sqlalchemy import Column, BIGINT, VARCHAR, DATETIME, Index
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.sql import func
from core.database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    name = Column(VARCHAR(50), nullable=False, unique=True, comment="角色名称")
    description = Column(VARCHAR(255), comment="角色描述")
    is_system = Column(TINYINT(1), nullable=False, default=0, comment="是否系统内置角色")
    created_at = Column(DATETIME, server_default=func.now())
    updated_at = Column(DATETIME, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_role_system", "is_system"),
        {"comment": "角色表"},
    )
