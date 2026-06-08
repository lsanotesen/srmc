"""子系统-程序分类关联表模型"""
from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship
from core.database import Base
from datetime import datetime


class SubsystemGroupRelation(Base):
    """子系统与程序分类的关联关系"""
    __tablename__ = 'subsystem_group_relations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    subsystem_id = Column(Integer, ForeignKey('subsystems.id', ondelete='CASCADE'), nullable=False, comment='子系统ID')
    group_id = Column(Integer, ForeignKey('service_groups.id', ondelete='CASCADE'), nullable=False, comment='程序分类ID')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')

    # 关系
    subsystem = relationship('Subsystem', back_populates='group_relations')
    group = relationship('ServiceGroup')

    __table_args__ = (
        UniqueConstraint('subsystem_id', 'group_id', name='uk_subsystem_group'),
        {'comment': '子系统与程序分类关联表'}
    )
