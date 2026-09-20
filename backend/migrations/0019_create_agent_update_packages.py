"""迁移：创建 Agent 更新包表（上传后持久保留，可复用）"""
from sqlalchemy import create_engine, inspect
from core.config import settings
from core.database import Base
# 导入模型以注册表
import models.agent_update  # noqa: F401

engine = create_engine(settings.DATABASE_URL)


def table_exists(name: str) -> bool:
    return name in inspect(engine).get_table_names()


def main():
    target = 'agent_update_packages'
    if not table_exists(target):
        Base.metadata.create_all(engine, tables=[Base.metadata.tables[target]])
        print(f"Created table {target}")
    else:
        print(f"{target} already exists")
    print("Migration 0019 completed")


main() if __name__ == "__main__" else None
