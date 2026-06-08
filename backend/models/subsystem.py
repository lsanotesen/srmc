from sqlalchemy import Column, BIGINT, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from core.database import Base
from datetime import datetime

class Subsystem(Base):
    """子系统模型"""
    __tablename__ = 'subsystems'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(BIGINT, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, comment='项目ID')
    subsystem_name = Column(String(100), nullable=False, comment='子系统名称')
    subsystem_code = Column(String(50), nullable=False, unique=True, comment='子系统编码')
    display_order = Column(Integer, default=0, comment='显示顺序')
    description = Column(Text, comment='描述')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关系
    project = relationship('Project', back_populates='subsystems')
    services = relationship('AppService', back_populates='subsystem')
    group_relations = relationship('SubsystemGroupRelation', back_populates='subsystem', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_project_id', 'project_id'),
        Index('idx_subsystem_code', 'subsystem_code'),
        {'comment': '子系统表'}
    )