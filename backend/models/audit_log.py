from sqlalchemy import Column, BIGINT, VARCHAR, TEXT, ENUM, DATETIME, ForeignKey
from core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(BIGINT, primary_key=True, autoincrement=True)
    user_id = Column(BIGINT, ForeignKey('users.id'))
    username = Column(VARCHAR(64), nullable=False)
    action = Column(ENUM('START', 'STOP', 'RESTART', 'SHELL', 'LOG', 'SQL', 'IMPORT', 'EXPORT', 'LOGIN', 'CREATE', 'UPDATE', 'DELETE'), nullable=False)
    service_id = Column(BIGINT, ForeignKey('services.id'))
    service_code = Column(VARCHAR(64))
    server_id = Column(BIGINT, ForeignKey('servers.id'))
    ip = Column(VARCHAR(45))
    result = Column(ENUM('success', 'failed'), nullable=False)
    output = Column(TEXT)
    duration = Column(BIGINT)
    created_at = Column(DATETIME, server_default="CURRENT_TIMESTAMP")
