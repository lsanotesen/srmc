"""迁移：扩展 service_container_configs.run_mode 枚举，新增 inactive（未启用/停止）

默认值仍为 permanent，老数据兼容不变。
"""
from sqlalchemy import create_engine, inspect, text
from core.config import settings

engine = create_engine(settings.DATABASE_URL)


def column_type(table: str, column: str):
    insp = inspect(engine)
    for col in insp.get_columns(table):
        if col['name'] == column:
            return str(col['type'])
    return None


def main():
    target = 'service_container_configs'
    if target not in inspect(engine).get_table_names():
        print(f"{target} not exists, skip")
        print("Migration 0022 completed")
        return

    current = column_type(target, 'run_mode')
    if current and 'inactive' in current:
        print(f"run_mode already supports inactive: {current}")
    else:
        with engine.begin() as conn:
            conn.execute(text(
                f"ALTER TABLE {target} MODIFY COLUMN run_mode "
                "ENUM('permanent','oneshot','inactive') NOT NULL DEFAULT 'permanent' "
                "COMMENT '运行类型: permanent=常驻服务, oneshot=一次性任务, inactive=未启用/停止'"
            ))
        print(f"Extended run_mode enum (was: {current})")
    print("Migration 0022 completed")


main() if __name__ == "__main__" else None
