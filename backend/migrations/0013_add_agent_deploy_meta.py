"""迁移：为 agents 表添加 Agent 自身部署元信息字段（deploy_type/deploy_dir/compose_file/binary_path）"""
from sqlalchemy import create_engine, inspect, text
from core.config import settings

engine = create_engine(settings.DATABASE_URL)

with engine.connect() as conn:
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('agents')]

    for col, ddl in [
        ("deploy_type", "VARCHAR(16)"),
        ("deploy_dir", "VARCHAR(256)"),
        ("compose_file", "VARCHAR(256)"),
        ("binary_path", "VARCHAR(256)"),
    ]:
        if col not in columns:
            conn.execute(text(f"ALTER TABLE agents ADD COLUMN {col} {ddl}"))
            print(f"Added {col} column to agents")
        else:
            print(f"{col} column already exists")

    conn.commit()

print("Migration 0013 completed")
