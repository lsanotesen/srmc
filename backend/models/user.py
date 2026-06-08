from sqlalchemy import Column, BIGINT, VARCHAR, DATETIME
from sqlalchemy.dialects.mysql import ENUM, TINYINT
from core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(BIGINT, primary_key=True, autoincrement=True)
    username = Column(VARCHAR(64), nullable=False, unique=True)
    password = Column(VARCHAR(256), nullable=False)
    role = Column(ENUM('ADMIN', 'OPS', 'DEV', 'READONLY'), nullable=False, default='READONLY')
    email = Column(VARCHAR(128))
    phone = Column(VARCHAR(20))
    is_active = Column(TINYINT(1), default=1)
    created_at = Column(DATETIME, server_default="CURRENT_TIMESTAMP")
    updated_at = Column(DATETIME, server_default="CURRENT_TIMESTAMP", onupdate="CURRENT_TIMESTAMP")
