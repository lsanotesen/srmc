from sqlalchemy import Column, BIGINT, VARCHAR, TEXT, DATETIME, ForeignKey
from sqlalchemy.dialects.mysql import ENUM
from core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(BIGINT, primary_key=True, autoincrement=True)
    user_id = Column(BIGINT, ForeignKey('users.id'))
    username = Column(VARCHAR(64), nullable=False)
    action = Column(ENUM('START', 'STOP', 'RESTART', 'SHELL', 'LOG', 'SQL', 'IMPORT', 'EXPORT', 'LOGIN', 'CREATE', 'UPDATE', 'DELETE', 'PROJECT_CREATE', 'PROJECT_UPDATE', 'PROJECT_DELETE', 'PROJECT_IMPORT', 'CREATE_PROJECT', 'DELETE_PROJECT', 'SERVICE_CREATE', 'SERVICE_UPDATE', 'SERVICE_DELETE', 'SERVICE_START', 'SERVICE_STOP', 'SERVICE_RESTART', 'SUBSYSTEM_CREATE', 'SUBSYSTEM_UPDATE', 'SUBSYSTEM_DELETE', 'SERVICE_GROUP_CREATE', 'SERVICE_GROUP_UPDATE', 'SERVICE_GROUP_DELETE', 'SERVICE_IMPORT'), nullable=False)
    service_id = Column(BIGINT, ForeignKey('services.id'))
    service_code = Column(VARCHAR(64))
    server_id = Column(BIGINT, ForeignKey('servers.id'))
    ip = Column(VARCHAR(45))
    result = Column(ENUM('success', 'failed', 'partial'), nullable=False)
    output = Column(TEXT)
    duration = Column(BIGINT)
    created_at = Column(DATETIME, server_default="CURRENT_TIMESTAMP")
