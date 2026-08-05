from sqlalchemy import Column, BIGINT, ForeignKey, DATETIME, Index, UniqueConstraint
from sqlalchemy.sql import func
from core.database import Base


class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    role_id = Column(BIGINT, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, comment="角色ID")
    created_at = Column(DATETIME, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uk_user_role"),
        Index("idx_ur_user", "user_id"),
        Index("idx_ur_role", "role_id"),
        {"comment": "用户-角色关联表"},
    )
