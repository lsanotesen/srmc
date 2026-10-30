"""迁移：servers 表新增 bmc_type / bmc_url / remark 列

背景：服务器管理需要补充带外管理（BMC/iDRAC/iLO）入口与备注信息。
按既定约束只保存带外类型和访问地址，不保存带外账号密码。

回滚快照：升级前记录 servers 表已有列名到
_snapshots/before_0029_server_bmc_remark_20261025.json
回滚逻辑：downgrade() 删除 bmc_type / bmc_url / remark 三列，其余列与数据不受影响。
"""
import json
import os

from sqlalchemy import create_engine, inspect, text

from core.config import settings

engine = create_engine(settings.DATABASE_URL)

TABLE = "servers"
COLUMNS = {
    "bmc_type": "VARCHAR(32) NULL",
    "bmc_url": "VARCHAR(512) NULL",
    "remark": "VARCHAR(255) NULL",
}

SNAPSHOT_PATH = os.path.join(
    os.path.dirname(__file__), "_snapshots",
    "before_0029_server_bmc_remark_20261025.json",
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

    with engine.begin() as conn:
        for column, column_def in COLUMNS.items():
            if column in existing:
                print(f"[skip] column exists: {column}")
                continue
            conn.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {column} {column_def}"))
            print(f"[apply] added column: {column}")


def downgrade():
    existing = _columns()
    with engine.begin() as conn:
        for column in COLUMNS:
            if column not in existing:
                print(f"[skip] column absent: {column}")
                continue
            conn.execute(text(f"ALTER TABLE {TABLE} DROP COLUMN {column}"))
            print(f"[rollback] dropped column: {column}")


def main():
    upgrade()
    print("Migration 0029 completed")


if __name__ == "__main__":
    main()
