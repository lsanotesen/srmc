from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from core.database import Base

class Process(Base):
    __tablename__ = 'processes'
    
    id = Column(Integer, primary_key=True, index=True)
    process_name = Column(String(100), nullable=False)
    process_code = Column(String(50), unique=True, nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'))
    language = Column(String(20), nullable=False)
    module = Column(String(100))
    environment = Column(String(20), nullable=False)
    ip = Column(String(50), nullable=False)
    port = Column(Integer)
    work_dir = Column(String(255))
    start_command = Column(String(500))
    stop_command = Column(String(500))
    check_type = Column(String(20))
    check_keyword = Column(String(100))
    status = Column(String(20), default='STOPPED')
    pid = Column(Integer)
    owner = Column(String(50))
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    project = relationship('Project', backref=backref('processes', lazy='noload'))
