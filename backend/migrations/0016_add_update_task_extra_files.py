"""迁移：agent_update_tasks 表新增 compose_file_content / config_file_content / service_file_content 列"""
from sqlalchemy import create_engine, text
from core.config import settings

engine = create_engine(settings.DATABASE_URL)


def main():
    with engine.connect() as conn:
        # 检查列是否存在
        row = conn.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agent_update_tasks' "
            "AND COLUMN_NAME = 'compose_file_content'"
        )).fetchone()
        if not row:
            conn.execute(text("ALTER TABLE agent_update_tasks ADD COLUMN compose_file_content TEXT COMMENT 'docker-compose.yml 内容'"))
            print("Added compose_file_content")
        else:
            print("compose_file_content already exists")

        row = conn.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agent_update_tasks' "
            "AND COLUMN_NAME = 'config_file_content'"
        )).fetchone()
        if not row:
            conn.execute(text("ALTER TABLE agent_update_tasks ADD COLUMN config_file_content TEXT COMMENT 'config.yaml 内容'"))
            print("Added config_file_content")
        else:
            print("config_file_content already exists")

        row = conn.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agent_update_tasks' "
            "AND COLUMN_NAME = 'service_file_content'"
        )).fetchone()
        if not row:
            conn.execute(text("ALTER TABLE agent_update_tasks ADD COLUMN service_file_content TEXT COMMENT 'srmc-agent.service 内容'"))
            print("Added service_file_content")
        else:
            print("service_file_content already exists")

        conn.commit()

    print("Migration 0016 completed")


main() if __name__ == "__main__" else None
