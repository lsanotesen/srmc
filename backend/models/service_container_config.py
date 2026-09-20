"""服务容器配置：容器级运行类型（常驻服务 / 一次性任务）

设计要点：
- 容器状态本身不落库（走 Redis），但 run_mode 是配置，必须持久化。
- 默认无记录 = permanent（常驻服务），因此历史数据无需回填，新容器自动按常驻处理。
- 只有管理员显式把某个容器改成 oneshot 才会产生记录。
"""
from sqlalchemy import Column, BIGINT, VARCHAR, DATETIME, UniqueConstraint, Index
from sqlalchemy.dialects.mysql import ENUM
from core.database import Base


class ServiceContainerConfig(Base):
    """容器级配置：按 (service_id, container_name) 唯一"""
    __tablename__ = 'service_container_configs'

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    service_id = Column(BIGINT, nullable=False, comment='所属服务ID(app_services.id)')
    container_name = Column(VARCHAR(255), nullable=False, comment='容器名称')
    run_mode = Column(
        ENUM('permanent', 'oneshot', 'inactive'),
        nullable=False,
        default='permanent',
        comment='运行类型: permanent=常驻服务, oneshot=一次性任务, inactive=未启用/停止',
    )
    updated_by = Column(VARCHAR(64), comment='最后修改人')
    created_at = Column(DATETIME)
    updated_at = Column(DATETIME)

    __table_args__ = (
        UniqueConstraint('service_id', 'container_name', name='uq_scc_service_container'),
        Index('idx_scc_service_id', 'service_id'),
        {'comment': '服务容器运行类型配置'},
    )
