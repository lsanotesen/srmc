"""导入批次模型：记录每次 Excel 导入的明细，支持精准撤销"""
from sqlalchemy import Column, BIGINT, INT, VARCHAR, TEXT, DATETIME
from sqlalchemy.dialects.mysql import ENUM
from core.database import Base


class ImportBatch(Base):
    """导入批次"""
    __tablename__ = 'import_batches'

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    batch_no = Column(VARCHAR(36), unique=True, nullable=False)
    filename = Column(VARCHAR(255))
    project_id = Column(BIGINT)
    project_name = Column(VARCHAR(100))
    subsystem_id = Column(INT, nullable=True)
    group_id = Column(INT, nullable=True)
    added_count = Column(INT, default=0)
    repaired_count = Column(INT, default=0)
    skipped_count = Column(INT, default=0)
    failed_count = Column(INT, default=0)
    auto_created_group_ids = Column(TEXT, comment='JSON数组:本次导入新建的分类ID')
    default_subsystem_created = Column(INT, default=0)
    pre_backup_record_id = Column(BIGINT, nullable=True, comment='导入前快照记录ID')
    status = Column(ENUM('active', 'reverted'), default='active')
    reverted_at = Column(DATETIME, nullable=True)
    reverted_by = Column(VARCHAR(64), nullable=True)
    created_by = Column(VARCHAR(64))
    created_at = Column(DATETIME)

    __table_args__ = {'comment': '导入批次表'}


class ImportBatchOperation(Base):
    """导入批次操作明细（撤销依据）"""
    __tablename__ = 'import_batch_operations'

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    batch_id = Column(BIGINT, nullable=False)
    op_type = Column(ENUM('created', 'repaired'), nullable=False)
    service_id = Column(BIGINT, nullable=False)
    old_project_id = Column(BIGINT, nullable=True)
    old_subsystem_id = Column(INT, nullable=True)
    old_group_id = Column(INT, nullable=True)

    __table_args__ = {'comment': '导入批次操作明细'}
