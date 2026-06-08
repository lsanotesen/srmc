"""Migration to change port field from Integer to String to support multiple ports"""
from sqlalchemy import text
from core.database import engine

def upgrade():
    """将端口字段从 Integer 改为 String"""
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE app_services MODIFY COLUMN port VARCHAR(255) COMMENT '程序端口（支持多个，逗号分隔）'"))

def downgrade():
    """回滚：将端口字段改回 Integer"""
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE app_services MODIFY COLUMN port INT COMMENT '程序端口'"))

if __name__ == "__main__":
    upgrade()
    print("Migration completed successfully")
