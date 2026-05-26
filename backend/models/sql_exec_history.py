from sqlalchemy import Column, BIGINT, VARCHAR, TEXT, DATETIME, ForeignKey
from core.database import Base

class SqlExecHistory(Base):
    __tablename__ = "sql_exec_history"
    
    id = Column(BIGINT, primary_key=True, autoincrement=True)
    user_id = Column(BIGINT, ForeignKey('users.id'))
    username = Column(VARCHAR(64), nullable=False)
    service_id = Column(BIGINT, ForeignKey('services.id'))
    service_code = Column(VARCHAR(64))
    sql_statement = Column(TEXT, nullable=False)
    execution_time = Column(BIGINT)
    result_count = Column(BIGINT)
    error_message = Column(TEXT)
    created_at = Column(DATETIME, server_default="CURRENT_TIMESTAMP")
