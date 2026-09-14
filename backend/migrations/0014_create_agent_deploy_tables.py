"""迁移：创建 Agent 安装包、批量装机任务及明细表"""
from sqlalchemy import create_engine, inspect
from core.config import settings
from core.database import Base
# 导入模型以注册表
import models.agent  # noqa: F401
import models.agent_update  # noqa: F401
import models.agent_deploy  # noqa: F401

engine = create_engine(settings.DATABASE_URL)


def table_exists(name: str) -> bool:
    return name in inspect(engine).get_table_names()


def main():
    target_tables = ['agent_packages', 'agent_deploy_tasks', 'agent_deploy_task_items']
    to_create = [t for t in target_tables if not table_exists(t)]
    if to_create:
        Base.metadata.create_all(engine, tables=[
            Base.metadata.tables[t] for t in to_create
        ])
        for t in to_create:
            print(f"Created table {t}")
    else:
        print("agent deploy tables already exist")
    print("Migration 0014 completed")


main() if __name__ == "__main__" else None
