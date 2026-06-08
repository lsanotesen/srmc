from sqlalchemy import Column, BIGINT, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base

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
    program_path = Column(String(500), nullable=False, comment='程序路径')
    start_script = Column(String(500), comment='启动脚本')
    stop_script = Column(String(500), comment='停止脚本')
    log_path = Column(String(500), comment='日志路径')
    port = Column(String(255), comment='程序端口（支持多个，逗号分隔）')
    owner = Column(String(100), comment='负责人')
    remark = Column(Text, comment='备注')
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    subsystem = relationship('Subsystem', back_populates='services')
    service_group = relationship('ServiceGroup', back_populates='services')
    
    __table_args__ = (
        Index('idx_subsystem_id', 'subsystem_id'),
        Index('idx_group_id', 'group_id'),
    )