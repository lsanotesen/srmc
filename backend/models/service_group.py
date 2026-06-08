from sqlalchemy import Column, Integer, String, Text, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from core.database import Base
from datetime import datetime

class ServiceGroup(Base):
    """程序分类模型（全局统一分类）"""
    __tablename__ = 'service_groups'

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_name = Column(String(100), nullable=False, comment='分类名称')
    group_code = Column(String(50), nullable=False, comment='分类编码')
    display_order = Column(Integer, default=0, comment='显示顺序')
    description = Column(Text, comment='描述')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关系
    services = relationship('AppService', back_populates='service_group')

    __table_args__ = (
        UniqueConstraint('group_code', name='uk_group_code'),
        {'comment': '程序分类表（全局统一）'}
    )
