from sqlalchemy import Column, INT, VARCHAR, TEXT, DATETIME, Index
from core.database import Base

class Program(Base):
    __tablename__ = "programs"
    
    id = Column(INT, primary_key=True, autoincrement=True)
    func_desc = Column(VARCHAR(255), nullable=False, comment='功能描述')
    module = Column(VARCHAR(100), comment='对应模块')
    ip = Column(VARCHAR(45), nullable=False, comment='服务器IP')
    username = Column(VARCHAR(100), nullable=False, comment='SSH用户名')
    password = Column(VARCHAR(500), nullable=False, comment='AES-256-GCM加密密码')
    program_path = Column(VARCHAR(500), nullable=False, comment='程序路径')
    start_script = Column(VARCHAR(500), comment='启动脚本')
    stop_script = Column(VARCHAR(500), comment='停止脚本')
    restart_script = Column(VARCHAR(500), comment='重启脚本')
    log_path = Column(VARCHAR(500), comment='日志路径')
    port = Column(INT, comment='程序端口')
    owner = Column(VARCHAR(100), comment='负责人')
    remark = Column(TEXT, comment='备注')
    created_at = Column(DATETIME, server_default="CURRENT_TIMESTAMP")
    updated_at = Column(DATETIME, server_default="CURRENT_TIMESTAMP", onupdate="CURRENT_TIMESTAMP")
    
    __table_args__ = (
        Index('idx_ip', 'ip'),
    )