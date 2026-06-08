from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base

class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, comment='项目名称')
    code = Column(String(50), comment='项目编码')
    description = Column(Text, comment='项目描述')
    
    # 关系
    subsystems = relationship('Subsystem', back_populates='project', cascade='all, delete-orphan')
