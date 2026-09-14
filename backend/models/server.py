from sqlalchemy import Column, BIGINT, VARCHAR, TEXT, DATETIME, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import ENUM
from core.database import Base

class Server(Base):
    __tablename__ = "servers"
    
    id = Column(BIGINT, primary_key=True, autoincrement=True)
    hostname = Column(VARCHAR(128), nullable=False)
    ip = Column(VARCHAR(45), nullable=False)
    ssh_port = Column(BIGINT, default=22)
    username = Column(VARCHAR(64), nullable=False)
    password = Column(TEXT)
    private_key = Column(TEXT)
    os_type = Column(ENUM('LINUX', 'UNIX'), default='LINUX')
    organization_id = Column(BIGINT, ForeignKey("organizations.id", ondelete="SET NULL"), comment="所属组织ID")
    created_at = Column(DATETIME, server_default="CURRENT_TIMESTAMP")
    updated_at = Column(DATETIME, server_default="CURRENT_TIMESTAMP", onupdate="CURRENT_TIMESTAMP")

    __table_args__ = (
        UniqueConstraint('ip', 'organization_id', name='uq_servers_ip_org'),
        Index('idx_servers_org', 'organization_id'),
    )
