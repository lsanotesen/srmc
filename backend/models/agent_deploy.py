"""Agent 批量装机：安装包、装机任务、每台主机执行明细"""
from sqlalchemy import Column, BIGINT, INT, VARCHAR, TEXT, DATETIME, Index
from sqlalchemy.dialects.mysql import ENUM
from core.database import Base


class AgentPackage(Base):
    """Agent 安装包（Docker 镜像 tar / 二进制可执行文件）"""
    __tablename__ = 'agent_packages'

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    package_id = Column(VARCHAR(36), unique=True, nullable=False, index=True, comment='包ID(UUID)')
    name = Column(VARCHAR(128), nullable=False, comment='包名称')
    package_type = Column(ENUM('docker', 'binary'), nullable=False, comment='包类型')
    version = Column(VARCHAR(64), nullable=False, comment='版本号')
    file_name = Column(VARCHAR(255), nullable=False, comment='原始文件名')
    file_path = Column(VARCHAR(500), nullable=False, comment='服务端存储路径')
    file_size = Column(BIGINT, default=0, comment='文件大小(bytes)')
    file_sha256 = Column(VARCHAR(64), nullable=False, comment='文件SHA256')
    description = Column(VARCHAR(500), comment='说明')
    created_by = Column(VARCHAR(64))
    created_at = Column(DATETIME)

    __table_args__ = (
        Index('idx_ap_type_version', 'package_type', 'version'),
        {'comment': 'Agent安装包'},
    )


class AgentDeployTask(Base):
    """批量装机任务主表（通过 SSH 推送安装到未纳管/旧版主机）"""
    __tablename__ = 'agent_deploy_tasks'

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    task_id = Column(VARCHAR(36), unique=True, nullable=False, comment='任务ID(UUID)')
    package_id = Column(VARCHAR(36), nullable=False, comment='安装包ID')
    package_type = Column(ENUM('docker', 'binary'), nullable=False, comment='部署方式')
    version = Column(VARCHAR(64), comment='版本号')

    # 部署参数
    deploy_dir = Column(VARCHAR(256), default='/etc/srmc-agent', comment='目标机部署目录')
    server_url = Column(VARCHAR(256), comment='Agent连接后端的WebSocket地址')

    # 可选：自定义部署文件（前端装机弹窗上传，覆盖系统模板）
    compose_file_content = Column(TEXT, comment='docker-compose.yml 自定义内容')
    config_file_content = Column(TEXT, comment='config.yaml 自定义内容')

    # 统计
    total_count = Column(INT, default=0)
    success_count = Column(INT, default=0)
    failed_count = Column(INT, default=0)
    running_count = Column(INT, default=0)
    waiting_count = Column(INT, default=0)
    cancelled_count = Column(INT, default=0)
    status = Column(ENUM('waiting', 'running', 'success', 'failed', 'partial', 'cancelled'), default='waiting')

    created_by = Column(VARCHAR(64))
    organization_id = Column(BIGINT, comment='创建者所属组织ID（凭据回写时的组织隔离）')
    created_at = Column(DATETIME)
    updated_at = Column(DATETIME)

    __table_args__ = (
        Index('idx_adt_status', 'status'),
        Index('idx_adt_created_at', 'created_at'),
        {'comment': 'Agent批量装机任务'},
    )


class AgentDeployTaskItem(Base):
    """批量装机明细（每台目标主机一条）"""
    __tablename__ = 'agent_deploy_task_items'

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    task_id = Column(VARCHAR(36), nullable=False, index=True)
    host = Column(VARCHAR(45), nullable=False, comment='目标主机IP')
    port = Column(INT, default=22, comment='SSH端口')
    ssh_username = Column(VARCHAR(100), comment='SSH用户名')
    ssh_password = Column(VARCHAR(500), comment='SSH密码（加密存储）')
    agent_name = Column(VARCHAR(128), comment='Agent名称（可选，留空用主机名）')
    agent_ip = Column(VARCHAR(45), comment='Agent IP（可选，多网卡时指定）')

    # 执行结果
    agent_uuid = Column(VARCHAR(64), comment='装机成功后注册的Agent UUID')
    hostname = Column(VARCHAR(128), comment='目标机主机名')
    status = Column(
        ENUM('waiting', 'running', 'success', 'failed', 'cancelled', 'skipped'),
        default='waiting',
    )
    current_step = Column(VARCHAR(255))
    progress = Column(INT, default=0)
    error_message = Column(TEXT)
    started_at = Column(DATETIME)
    finished_at = Column(DATETIME)
    created_at = Column(DATETIME)

    __table_args__ = (
        Index('idx_adti_task_id', 'task_id'),
        Index('idx_adti_host', 'host'),
        {'comment': 'Agent批量装机明细'},
    )
