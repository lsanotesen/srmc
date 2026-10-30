from sqlalchemy import Column, BIGINT, VARCHAR, TEXT, DATETIME, ForeignKey, Index, UniqueConstraint, Boolean, text
from sqlalchemy.dialects.mysql import ENUM
from core.database import Base

class Server(Base):
    __tablename__ = "servers"
    
    id = Column(BIGINT, primary_key=True, autoincrement=True)
    hostname = Column(VARCHAR(128), nullable=False)
    ip = Column(VARCHAR(45), nullable=False)
    ssh_port = Column(BIGINT, default=22)
    username = Column(VARCHAR(64), nullable=False)
    password = Column(TEXT)
    private_key = Column(TEXT)
    os_type = Column(ENUM('LINUX', 'UNIX'), default='LINUX')
    # 带外管理（BMC/iDRAC/iLO）：只保存类型与访问地址，不保存带外账号密码
    bmc_type = Column(VARCHAR(32), comment="带外管理类型：IPMI/iDRAC/iLO/OTHER")
    bmc_url = Column(VARCHAR(512), comment="带外管理访问地址（完整 http(s) URL）")
    remark = Column(VARCHAR(255), comment="备注")
    organization_id = Column(BIGINT, ForeignKey("organizations.id", ondelete="SET NULL"), comment="所属组织ID")
    created_at = Column(DATETIME, server_default=text("CURRENT_TIMESTAMP"))
    # 注意：onupdate 必须是 text()，直接写字符串会被当作字面量 'CURRENT_TIMESTAMP' 导致更新失败
    updated_at = Column(DATETIME, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint('ip', 'organization_id', name='uq_servers_ip_org'),
        Index('idx_servers_org', 'organization_id'),
    )


class ServerSshAccount(Base):
    """服务器 SSH 账号（一台服务器可配置多个账号）。

    servers.username/password/private_key 保留为默认账号的兼容镜像：
    默认账号变更时同步写回 servers，Agent 部署等既有流程无需改动；
    非默认账号仅存于本表。
    """
    __tablename__ = "server_ssh_accounts"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    server_id = Column(BIGINT, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, comment="所属服务器ID")
    username = Column(VARCHAR(64), nullable=False, comment="SSH 用户名")
    password = Column(TEXT, comment="密码（AES-GCM 密文）")
    private_key = Column(TEXT, comment="私钥（AES-GCM 密文）")
    is_default = Column(Boolean, nullable=False, default=False, comment="是否默认账号")
    remark = Column(VARCHAR(255), comment="备注")
    created_at = Column(DATETIME, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DATETIME, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint('server_id', 'username', name='uq_server_ssh_account'),
        Index('idx_ssh_accounts_server', 'server_id'),
    )
