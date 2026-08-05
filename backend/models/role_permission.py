from sqlalchemy import Column, BIGINT, ForeignKey, DATETIME, Index, UniqueConstraint
from sqlalchemy.sql import func
from core.database import Base


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    role_id = Column(BIGINT, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, comment="角色ID")
    permission_id = Column(BIGINT, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, comment="权限ID")
    created_at = Column(DATETIME, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uk_role_perm"),
        Index("idx_rp_role", "role_id"),
        Index("idx_rp_perm", "permission_id"),
        {"comment": "角色-权限关联表"},
    )
