"""数据库备份模型"""
from sqlalchemy import Column, BIGINT, INT, VARCHAR, TEXT, DATETIME, Time
from sqlalchemy.dialects.mysql import ENUM
from core.database import Base


class DbBackupConfig(Base):
    """数据库备份配置（单行记录）"""
    __tablename__ = 'db_backup_configs'

    id = Column(INT, primary_key=True, autoincrement=True)
    enabled = Column(INT, default=0, comment='定时备份开关')
    schedule_type = Column(ENUM('daily', 'weekly'), default='daily', comment='调度类型')
    schedule_time = Column(Time, default=None, comment='执行时间')
    week_day = Column(INT, default=1, comment='weekly时生效 0=周一..6=周日')
    retention_count = Column(INT, default=10, comment='保留份数')
    last_run_at = Column(DATETIME, nullable=True, comment='上次执行时间')
    updated_at = Column(DATETIME, nullable=True)

    __table_args__ = {'comment': '数据库备份配置'}


class DbBackupRecord(Base):
    """备份记录"""
    __tablename__ = 'db_backup_records'

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    filename = Column(VARCHAR(255), nullable=False)
    file_path = Column(VARCHAR(500), nullable=False)
    file_size = Column(BIGINT, default=0)
    backup_type = Column(
        ENUM('manual', 'scheduled', 'pre_import', 'pre_restore'),
        default='manual')
    status = Column(ENUM('running', 'success', 'failed'), default='running')
    table_count = Column(INT, default=0)
    row_count = Column(BIGINT, default=0)
    duration_ms = Column(INT, default=0)
    error_message = Column(TEXT, nullable=True)
    created_by = Column(VARCHAR(64))
    created_at = Column(DATETIME, nullable=True)

    __table_args__ = {'comment': '数据库备份记录'}
