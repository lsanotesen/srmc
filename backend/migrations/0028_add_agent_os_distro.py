"""迁移：agents 表新增 os_distro 列（Agent 上报操作系统发行版）

背景：agents.os 取自 gopsutil host.Info().OS，恒为 "linux"，无法体现
CentOS 7.9 / Ubuntu 22.04 这类发行版；Agent 改为读取宿主机 os-release 上报
真实发行版字符串，本迁移只新增一列用于存储。

回滚快照：升级前记录 agents 表已有列名到 _snapshots/before_0028_agent_os_distro_20261020.json
回滚逻辑：downgrade() 删除 os_distro 列，其余列与数据不受影响。
"""
import json
import os

from sqlalchemy import create_engine, inspect, text

from core.config import settings

engine = create_engine(settings.DATABASE_URL)

TABLE = "agents"
COLUMN = "os_distro"
COLUMN_DEF = "VARCHAR(128) NULL"

SNAPSHOT_PATH = os.path.join(
    os.path.dirname(__file__), "_snapshots",
    "before_0028_agent_os_distro_20261020.json",
)


def _columns():
    return [c["name"] for c in inspect(engine).get_columns(TABLE)]


def upgrade():
    existing = _columns()

    if not os.path.exists(SNAPSHOT_PATH):
        os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump({"table": TABLE, "columns_before": existing}, f,
                      ensure_ascii=False, indent=2)
        print(f"[snapshot] {SNAPSHOT_PATH}")

    if COLUMN in existing:
        print(f"[skip] column exists: {COLUMN}")
        return

    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} {COLUMN_DEF}"))
    print(f"[apply] added column: {COLUMN}")


def downgrade():
    if COLUMN not in _columns():
        print(f"[skip] column absent: {COLUMN}")
        return

    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {TABLE} DROP COLUMN {COLUMN}"))
    print(f"[rollback] dropped column: {COLUMN}")


def main():
    upgrade()
    print("Migration 0028 completed")


if __name__ == "__main__":
    main()
