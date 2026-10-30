"""迁移：创建告警记录表 alert_records（告警中心基础版）

回滚快照：本表为新增表，升级前不存在；升级后仅新增该表，不改动任何既有表结构。
回滚逻辑：downgrade() 直接 DROP 该表即可还原；不会影响其他表数据。
"""
from sqlalchemy import create_engine, inspect, text
from core.config import settings
from core.database import Base
# 导入模型以注册表
import models.alert_record  # noqa: F401

engine = create_engine(settings.DATABASE_URL)

TARGET = 'alert_records'


def table_exists(name: str) -> bool:
    return name in inspect(engine).get_table_names()


def upgrade():
    if not table_exists(TARGET):
        Base.metadata.create_all(engine, tables=[Base.metadata.tables[TARGET]])
        print(f"Created table {TARGET}")
    else:
        print(f"{TARGET} already exists")


def downgrade():
    """回滚：删除告警记录表（仅新增表，回滚不影响既有数据）"""
    if table_exists(TARGET):
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE {TARGET}"))
        print(f"Dropped table {TARGET}")
    else:
        print(f"{TARGET} not exists")


def main():
    upgrade()
    print("Migration 0027 completed")


if __name__ == "__main__":
    main()
