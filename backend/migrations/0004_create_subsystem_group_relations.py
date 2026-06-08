"""Migration to create subsystem_group_relations table."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.config import settings

def migrate():
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.begin() as conn:
        # 创建子系统-分类关联表
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS subsystem_group_relations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                subsystem_id INT NOT NULL COMMENT '子系统ID',
                group_id INT NOT NULL COMMENT '程序分类ID',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                FOREIGN KEY (subsystem_id) REFERENCES subsystems(id) ON DELETE CASCADE,
                FOREIGN KEY (group_id) REFERENCES service_groups(id) ON DELETE CASCADE,
                UNIQUE KEY uk_subsystem_group (subsystem_id, group_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='子系统与程序分类关联表'
        """))
        
    print("Migration completed successfully: subsystem_group_relations table created")

if __name__ == "__main__":
    migrate()
