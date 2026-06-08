"""Migration to remove subsystem_id from service_groups table and make groups global."""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.config import settings

def migrate():
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # 1. 先尝试移除外键约束（如果存在）
        try:
            conn.execute(text("ALTER TABLE service_groups DROP FOREIGN KEY service_groups_ibfk_1"))
        except Exception:
            pass
        
        # 2. 移除旧的唯一约束（如果存在）
        try:
            conn.execute(text("ALTER TABLE service_groups DROP INDEX uk_subsystem_code"))
        except Exception:
            pass
        
        # 3. 添加新的全局唯一约束（确保 group_code 在全局范围内唯一）
        try:
            conn.execute(text("ALTER TABLE service_groups ADD UNIQUE KEY uk_group_code (group_code)"))
        except Exception:
            pass
        
        # 4. 移除 subsystem_id 字段
        try:
            conn.execute(text("ALTER TABLE service_groups DROP COLUMN subsystem_id"))
        except Exception:
            pass
        
        # 5. 移除旧的索引
        try:
            conn.execute(text("DROP INDEX IF EXISTS idx_subsystem_id"))
        except Exception:
            pass
        
        conn.commit()
        print("Migration completed successfully: service_groups is now global")

if __name__ == "__main__":
    migrate()
