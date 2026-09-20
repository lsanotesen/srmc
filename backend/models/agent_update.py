"""Agent 批量更新任务模型：更新包 + 任务主表 + 每台 Agent 执行明细"""
from sqlalchemy import Column, BIGINT, INT, VARCHAR, TEXT, DATETIME, Index
from sqlalchemy.dialects.mysql import ENUM
from core.database import Base


class AgentUpdatePackage(Base):
    """Agent 更新包（Docker 镜像 tar / 二进制文件），上传后持久保留可复用"""
    __tablename__ = 'agent_update_packages'

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    package_id = Column(VARCHAR(36), unique=True, nullable=False, index=True, comment='包ID(UUID)')
    name = Column(VARCHAR(128), nullable=False, comment='包名称')
    update_type = Column(ENUM('docker', 'binary'), nullable=False, comment='更新类型')
    version = Column(VARCHAR(64), comment='版本号/镜像Tag')
    file_name = Column(VARCHAR(255), nullable=False, comment='原始文件名')
    file_path = Column(VARCHAR(500), nullable=False, comment='服务端存储路径')
    file_size = Column(BIGINT, default=0, comment='文件大小(bytes)')
    file_sha256 = Column(VARCHAR(64), nullable=False, comment='文件SHA256')
    description = Column(VARCHAR(500), comment='说明')
    created_by = Column(VARCHAR(64))
    created_at = Column(DATETIME)

    __table_args__ = (
        Index('idx_aup_type_version', 'update_type', 'version'),
        {'comment': 'Agent更新包'},
    )


class AgentUpdateTask(Base):
    """批量更新任务主表"""
    __tablename__ = 'agent_update_tasks'

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    task_id = Column(VARCHAR(36), unique=True, nullable=False, comment='任务ID(UUID)')
    update_type = Column(ENUM('docker', 'binary'), nullable=False, comment='更新类型')

    # 文件信息
    file_name = Column(VARCHAR(255), nullable=False, comment='原始文件名')
    file_path = Column(VARCHAR(500), nullable=False, comment='服务端临时文件路径')
    file_size = Column(BIGINT, default=0, comment='文件大小(bytes)')
    file_sha256 = Column(VARCHAR(64), nullable=False, comment='文件SHA256')
    version = Column(VARCHAR(64), comment='版本号/镜像Tag')

    # Docker 镜像更新参数
    image_name = Column(VARCHAR(255), comment='镜像名称')
    image_tag = Column(VARCHAR(100), comment='镜像Tag')
    container_name = Column(VARCHAR(128), comment='目标容器名(可选，用于重启)')

    # 二进制更新参数
    binary_target_path = Column(VARCHAR(500), comment='目标路径')
    binary_service_name = Column(VARCHAR(128), comment='服务名称/启动方式')
    backup_before_update = Column(INT, default=1, comment='更新前备份 1/0')
    auto_stop_old = Column(INT, default=1, comment='自动停止旧程序 1/0')
    auto_start_after = Column(INT, default=1, comment='更新后自动启动 1/0')

    # 可选：同步配置文件内容（从前端批量更新弹窗上传）
    compose_file_content = Column(TEXT, comment='docker-compose.yml 内容')
    config_file_content = Column(TEXT, comment='config.yaml 内容')
    service_file_content = Column(TEXT, comment='srmc-agent.service 内容')

    # 统计
    total_count = Column(INT, default=0, comment='目标总数')
    success_count = Column(INT, default=0)
    failed_count = Column(INT, default=0)
    running_count = Column(INT, default=0)
    waiting_count = Column(INT, default=0)
    cancelled_count = Column(INT, default=0)
    status = Column(ENUM('waiting', 'running', 'success', 'failed', 'partial', 'cancelled'), default='waiting')

    created_by = Column(VARCHAR(64))
    created_at = Column(DATETIME)
    updated_at = Column(DATETIME)

    __table_args__ = (
        Index('idx_aut_status', 'status'),
        Index('idx_aut_created_at', 'created_at'),
        {'comment': 'Agent批量更新任务'},
    )


class AgentUpdateTaskItem(Base):
    """批量更新任务明细（每台 Agent 一条执行记录）"""
    __tablename__ = 'agent_update_task_items'

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    task_id = Column(VARCHAR(36), nullable=False, index=True)
    agent_uuid = Column(VARCHAR(64), nullable=False)
    hostname = Column(VARCHAR(128))
    ip = Column(VARCHAR(45))
    status = Column(
        ENUM('waiting', 'running', 'success', 'failed', 'cancelled', 'skipped'),
        default='waiting',
    )
    current_step = Column(VARCHAR(255), comment='当前步骤')
    progress = Column(INT, default=0, comment='进度 0-100')
    error_message = Column(TEXT)
    started_at = Column(DATETIME)
    finished_at = Column(DATETIME)
    created_at = Column(DATETIME)

    __table_args__ = (
        Index('idx_auti_task_id', 'task_id'),
        Index('idx_auti_agent', 'agent_uuid'),
        {'comment': 'Agent批量更新明细'},
    )