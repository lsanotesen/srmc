from sqlalchemy import Column, BIGINT, VARCHAR, DATETIME, ForeignKey, Index, text
from sqlalchemy.dialects.mysql import ENUM, TINYINT
from core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    username = Column(VARCHAR(64), nullable=False, unique=True)
    password = Column(VARCHAR(256), nullable=False)
    role = Column(ENUM("SUPER_ADMIN", "ORG_ADMIN", "DEPT_ADMIN", "DEPT_MEMBER", "READONLY"), nullable=False, default="READONLY")
    email = Column(VARCHAR(128))
    phone = Column(VARCHAR(20))
    is_active = Column(TINYINT(1), default=1)
    organization_id = Column(BIGINT, ForeignKey("organizations.id", ondelete="SET NULL"), comment="所属组织ID")
    department_id = Column(BIGINT, ForeignKey("departments.id", ondelete="SET NULL"), comment="所属部门ID")
    job_title = Column(VARCHAR(100), comment="职位")
    status = Column(TINYINT(1), nullable=False, default=1, comment="状态: 1-启用, 0-禁用")
    created_at = Column(DATETIME, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DATETIME, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_user_org", "organization_id"),
        Index("idx_user_dept", "department_id"),
    )
