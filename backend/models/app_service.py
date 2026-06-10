from sqlalchemy import Column, BIGINT, Integer, String, Text, DateTime, ForeignKey, Index, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base

# 服务类型枚举
ServiceType = Enum(
    'HOST_APP', 
    'DOCKER', 
    'ES', 
    'SOLR', 
    'REDIS', 
    'MYSQL', 
    'POSTGRESQL', 
    'KAFKA', 
    'ROCKETMQ', 
    'RABBITMQ', 
    'NGINX', 
    'AI_MODEL',
    name='service_type'
)

# 部署方式枚举
DeployType = Enum(
    'HOST', 
    'DOCKER',
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
    
    # 新增字段
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
    
    # 集群相关字段
    cluster_name = Column(String(255), comment='集群名称')
    node_count = Column(Integer, comment='节点数量')
    master_node = Column(String(45), comment='Master节点IP')
    data_nodes = Column(String(500), comment='Data节点列表')
    
    # Redis相关字段
    redis_role = Column(String(50), comment='Redis角色')
    redis_memory_usage = Column(String(50), comment='内存使用率')
    redis_key_count = Column(BIGINT, comment='Key数量')
    
    # MySQL相关字段
    mysql_version = Column(String(50), comment='MySQL版本')
    mysql_connection_count = Column(Integer, comment='连接数')
    mysql_slave_status = Column(String(50), comment='主从状态')
    mysql_db_count = Column(Integer, comment='数据库数量')
    
    # 监控状态
    status = Column(String(50), default='stopped', comment='运行状态：running/stopped/error/warning')
    cpu_usage = Column(String(20), comment='CPU使用率')
    memory_usage = Column(String(20), comment='内存使用率')
    disk_usage = Column(String(20), comment='磁盘使用率')
    network_io = Column(String(100), comment='网络IO')
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    subsystem = relationship('Subsystem', back_populates='services')
    service_group = relationship('ServiceGroup', back_populates='services')
    
    __table_args__ = (
        Index('idx_subsystem_id', 'subsystem_id'),
        Index('idx_group_id', 'group_id'),
    )