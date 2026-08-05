from sqlalchemy import Column, BIGINT, Integer, String, Text, DateTime, ForeignKey, Index, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base

# 服务类型枚举
ServiceType = Enum(
    'HOST_APP', 
    'DOCKER',
    'DOCKER_COMPOSE',
    name='service_type'
)

# 部署方式枚举
DeployType = Enum(
    'HOST', 
    'DOCKER',
    'DOCKER_COMPOSE',
    name='deploy_type'
)

class AppService(Base):
    __tablename__ = 'app_services'
    
    id = Column(BIGINT, primary_key=True, autoincrement=True)
    project_id = Column(BIGINT, nullable=False, comment='所属项目ID')
    subsystem_id = Column(Integer, ForeignKey('subsystems.id', ondelete='SET NULL'), nullable=True, comment='子系统ID')
    group_id = Column(Integer, ForeignKey('service_groups.id', ondelete='SET NULL'), nullable=True, comment='程序分类ID')
    func_desc = Column(String(255), nullable=False, comment='功能描述')
    module = Column(String(100), comment='对应模块')
    ip = Column(String(45), nullable=False, comment='服务器IP')
    ssh_port = Column(Integer, default=22, comment='SSH端口，默认22')
    username = Column(String(100), nullable=False, comment='SSH用户名')
    password = Column(String(500), nullable=False, comment='AES-256-GCM加密密码')
    program_path = Column(String(500), comment='程序路径')
    start_script = Column(String(500), comment='启动脚本')
    stop_script = Column(String(500), comment='停止脚本')
    log_path = Column(String(500), comment='日志路径')
    port = Column(String(255), comment='程序端口（支持多个，逗号分隔）')
    owner = Column(String(100), comment='负责人')
    remark = Column(Text, comment='备注')
    
    # 服务类型和部署方式
    service_type = Column(ServiceType, default='HOST_APP', comment='服务类型')
    deploy_type = Column(DeployType, default='HOST', comment='部署方式')
    instance_name = Column(String(255), comment='运行实例名称')
    
    # Docker相关字段
    container_name = Column(String(255), comment='容器名称')
    image_name = Column(String(255), comment='镜像名称')
    image_tag = Column(String(100), comment='镜像版本')
    container_id = Column(String(64), comment='容器ID')
    port_mapping = Column(String(500), comment='端口映射')
    volume_mapping = Column(String(1000), comment='Volume挂载')
    network_mode = Column(String(100), comment='网络模式')
    log_type = Column(String(50), comment='日志类型: HOST_DIR/DOCKER_LOGS')
    
    # Agent相关字段
    agent_uuid = Column(String(64), comment='关联的Agent UUID')
    health_url = Column(String(500), comment='健康检查URL')
    pid_file = Column(String(500), comment='PID文件路径')
    

    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系 - 使用 lazy='select' 延迟加载避免循环导入问题
    subsystem = relationship('Subsystem', back_populates='services', lazy='select')
    service_group = relationship('ServiceGroup', back_populates='services', lazy='select')
    
    __table_args__ = (
        Index('idx_subsystem_id', 'subsystem_id'),
        Index('idx_group_id', 'group_id'),
    )