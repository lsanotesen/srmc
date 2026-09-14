"""迁移：servers 按组织隔离（organization_id + 复合唯一）；agent_deploy_tasks 记录组织"""
from sqlalchemy import create_engine, text
from core.config import settings

engine = create_engine(settings.DATABASE_URL)


def _column_exists(conn, table, column):
    return conn.execute(text(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
    ), {"t": table, "c": column}).fetchone() is not None


def _index_exists(conn, table, index):
    return conn.execute(text(
        "SELECT INDEX_NAME FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND INDEX_NAME = :i"
    ), {"t": table, "i": index}).fetchone() is not None


def main():
    with engine.connect() as conn:
        # 1. servers 新增 organization_id + 组织索引
        if not _column_exists(conn, "servers", "organization_id"):
            conn.execute(text(
                "ALTER TABLE servers ADD COLUMN organization_id BIGINT NULL COMMENT '所属组织ID'"
            ))
            print("Added servers.organization_id")
        else:
            print("servers.organization_id already exists")

        if not _index_exists(conn, "servers", "idx_servers_org"):
            conn.execute(text("ALTER TABLE servers ADD INDEX idx_servers_org (organization_id)"))
            print("Added idx_servers_org")

        # 2. agent_deploy_tasks 新增 organization_id
        if not _column_exists(conn, "agent_deploy_tasks", "organization_id"):
            conn.execute(text(
                "ALTER TABLE agent_deploy_tasks ADD COLUMN organization_id BIGINT NULL COMMENT '创建者所属组织ID'"
            ))
            print("Added agent_deploy_tasks.organization_id")
        else:
            print("agent_deploy_tasks.organization_id already exists")

        # 3. 去掉 servers.ip 的全局唯一索引，改为 (ip, organization_id) 复合唯一
        unique_rows = conn.execute(text(
            "SELECT INDEX_NAME FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'servers' "
            "AND COLUMN_NAME = 'ip' AND NON_UNIQUE = 0 AND INDEX_NAME != 'uq_servers_ip_org'"
        )).fetchall()
        for row in unique_rows:
            conn.execute(text("ALTER TABLE servers DROP INDEX %s" % row[0]))
            print(f"Dropped unique index {row[0]} on servers.ip")

        if not _index_exists(conn, "servers", "uq_servers_ip_org"):
            conn.execute(text(
                "ALTER TABLE servers ADD UNIQUE KEY uq_servers_ip_org (ip, organization_id)"
            ))
            print("Added uq_servers_ip_org (ip, organization_id)")

        conn.commit()

    print("Migration 0018 completed")


main() if __name__ == "__main__" else None