"""迁移：创建 service_container_configs 表（容器级运行类型配置）

默认无记录 = permanent（常驻服务），历史数据无需回填。
"""
from sqlalchemy import create_engine, inspect
from core.config import settings
from core.database import Base
# 导入模型以注册表
import models.service_container_config  # noqa: F401

engine = create_engine(settings.DATABASE_URL)


def table_exists(name: str) -> bool:
    return name in inspect(engine).get_table_names()


def main():
    target = 'service_container_configs'
    if not table_exists(target):
        Base.metadata.create_all(engine, tables=[Base.metadata.tables[target]])
        print(f"Created table {target}")
    else:
        print(f"{target} already exists")
    print("Migration 0021 completed")


main() if __name__ == "__main__" else None
