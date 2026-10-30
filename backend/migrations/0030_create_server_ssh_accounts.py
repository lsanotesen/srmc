"""迁移：新增 server_ssh_accounts 表，支持一台服务器配置多个 SSH 账号

背景：服务器管理页的「SSH 账号」列需要支持多账号查看与管理。
设计：新增 server_ssh_accounts 表作为账号集合；servers.username/password/private_key
保留为“默认账号”的兼容镜像，Agent 部署、监控等既有流程继续读取原字段，无需改动。

历史数据回填：已有密码或私钥的服务器，按原用户名生成一条默认账号记录；
没有凭据的服务器不回填（页面显示“未配置”）。

回滚快照：升级前记录 servers 表列名与待回填服务器数量到
_snapshots/before_0030_server_ssh_accounts_20261029.json
回滚逻辑：downgrade() 直接删除 server_ssh_accounts 表，servers 原字段不受影响。
"""
import json
import os

from sqlalchemy import create_engine, inspect, text

from core.config import settings

engine = create_engine(settings.DATABASE_URL)

TABLE = "server_ssh_accounts"

SNAPSHOT_PATH = os.path.join(
    os.path.dirname(__file__), "_snapshots",
    "before_0030_server_ssh_accounts_20261029.json",
)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS server_ssh_accounts (
    id BIGINT NOT NULL AUTO_INCREMENT,
    server_id BIGINT NOT NULL COMMENT '所属服务器ID',
    username VARCHAR(64) NOT NULL COMMENT 'SSH 用户名',
    password TEXT COMMENT '密码（AES-GCM 密文）',
    private_key TEXT COMMENT '私钥（AES-GCM 密文）',
    is_default TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否默认账号',
    remark VARCHAR(255) COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_server_ssh_account (server_id, username),
    KEY idx_ssh_accounts_server (server_id),
    CONSTRAINT fk_ssh_accounts_server FOREIGN KEY (server_id) REFERENCES servers (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='服务器 SSH 账号'
"""

# servers 表使用 utf8mb4_unicode_ci；若表已存在但排序规则不一致，先统一再回填
FIX_COLLATION_SQL = (
    f"ALTER TABLE {TABLE} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
)

# 只为已有凭据的服务器回填默认账号；重复执行不会产生重复行
BACKFILL_SQL = """
INSERT INTO server_ssh_accounts (server_id, username, password, private_key, is_default)
SELECT s.id, s.username, s.password, s.private_key, 1
FROM servers s
WHERE ((s.password IS NOT NULL AND s.password <> '')
    OR (s.private_key IS NOT NULL AND s.private_key <> ''))
  AND NOT EXISTS (
    SELECT 1 FROM server_ssh_accounts a
    WHERE a.server_id = s.id AND a.username = s.username
  )
"""


def _table_exists():
    return TABLE in inspect(engine).get_table_names()


def _write_snapshot(existing_columns):
    if os.path.exists(SNAPSHOT_PATH):
        return
    os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
    with engine.connect() as conn:
        pending = conn.execute(text("""
            SELECT COUNT(*) FROM servers
            WHERE (password IS NOT NULL AND password <> '')
               OR (private_key IS NOT NULL AND private_key <> '')
        """)).scalar()
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "table": TABLE,
            "servers_columns_before": existing_columns,
            "backfill_candidates": int(pending or 0),
        }, f, ensure_ascii=False, indent=2)
    print(f"[snapshot] {SNAPSHOT_PATH}")


def upgrade():
    existing_columns = [c["name"] for c in inspect(engine).get_columns("servers")]
    _write_snapshot(existing_columns)

    existed = _table_exists()
    with engine.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))
        if not existed:
            print(f"[apply] created table: {TABLE}")
        else:
            print(f"[skip] table exists: {TABLE}")
            conn.execute(text(FIX_COLLATION_SQL))
        result = conn.execute(text(BACKFILL_SQL))
        print(f"[apply] backfilled default accounts: {result.rowcount}")


def downgrade():
    if not _table_exists():
        print(f"[skip] table absent: {TABLE}")
        return
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE {TABLE}"))
    print(f"[rollback] dropped table: {TABLE}")


def main():
    upgrade()
    print("Migration 0030 completed")


if __name__ == "__main__":
    main()
