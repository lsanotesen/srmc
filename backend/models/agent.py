from sqlalchemy import Column, VARCHAR, TEXT, DATETIME, Integer, BIGINT, JSON, Boolean
from sqlalchemy.sql import func
from core.database import Base

class Agent(Base):
    __tablename__ = 'agents'
    
    id = Column(BIGINT, primary_key=True, autoincrement=True)
    uuid = Column(VARCHAR(64), nullable=False, unique=True, index=True)
    hostname = Column(VARCHAR(128), nullable=False)
    ip = Column(VARCHAR(45), nullable=False)
    os = Column(VARCHAR(64))
    os_distro = Column(VARCHAR(128))
    kernel = Column(VARCHAR(128))
    arch = Column(VARCHAR(32))
    cpu_model = Column(VARCHAR(256))
    cpu_cores = Column(Integer)
    memory_total = Column(BIGINT)
    agent_version = Column(VARCHAR(32))
    capabilities = Column(JSON)
    tags = Column(JSON)
    status = Column(VARCHAR(32), default='offline')
    last_heartbeat = Column(DATETIME)
    created_at = Column(DATETIME, default=func.now())
    updated_at = Column(DATETIME, default=func.now(), onupdate=func.now())
    
    # Agent 控制相关字段（用于远程启停 Agent 进程）
    ssh_port = Column(Integer, default=22, comment='SSH端口')
    ssh_username = Column(VARCHAR(100), comment='SSH用户名')
    ssh_password = Column(VARCHAR(500), comment='SSH密码（加密存储）')
    service_name = Column(VARCHAR(128), default='srmc-agent', comment='systemd服务名称')

    # Agent 自身部署元信息（注册时由 Agent 上报，批量更新下发时使用）
    deploy_type = Column(VARCHAR(16), comment='部署方式: docker/binary')
    deploy_dir = Column(VARCHAR(256), comment='Agent根部署目录')
    compose_file = Column(VARCHAR(256), comment='docker-compose.yml路径')
    binary_path = Column(VARCHAR(256), comment='二进制文件路径')