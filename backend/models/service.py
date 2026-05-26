from sqlalchemy import Column, BIGINT, VARCHAR, TEXT, ENUM, DATETIME, ForeignKey
from sqlalchemy.orm import relationship
from core.database import Base

class Service(Base):
    __tablename__ = "services"
    
    id = Column(BIGINT, primary_key=True, autoincrement=True)
    service_name = Column(VARCHAR(128), nullable=False)
    service_code = Column(VARCHAR(64), nullable=False, unique=True)
    service_type = Column(ENUM('APP', 'NGINX', 'REDIS', 'MYSQL', 'KINGBASE', 'DAMENG', 'ELASTICSEARCH', 'RABBITMQ', 'OTHER'), nullable=False)
    module = Column(VARCHAR(64))
    environment = Column(ENUM('DEV', 'TEST', 'STAGING', 'PROD'), nullable=False)
    server_id = Column(BIGINT, ForeignKey('servers.id'))
    ip = Column(VARCHAR(45), nullable=False)
    port = Column(BIGINT)
    service_path = Column(VARCHAR(512))
    work_dir = Column(VARCHAR(512))
    start_script = Column(VARCHAR(512))
    stop_script = Column(VARCHAR(512))
    restart_script = Column(VARCHAR(512))
    log_path = Column(VARCHAR(512))
    check_type = Column(ENUM('PROCESS', 'PORT', 'PID', 'SCRIPT', 'HTTP', 'TCP'))
    check_keyword = Column(VARCHAR(256))
    pid_file = Column(VARCHAR(512))
    owner = Column(VARCHAR(64))
    remark = Column(TEXT)
    extra_config = Column(TEXT)
    created_at = Column(DATETIME, server_default="CURRENT_TIMESTAMP")
    updated_at = Column(DATETIME, server_default="CURRENT_TIMESTAMP", onupdate="CURRENT_TIMESTAMP")
    
    server = relationship("Server")
