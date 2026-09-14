"""迁移：agent_deploy_tasks 表新增 compose_file_content / config_file_content 列"""
from sqlalchemy import create_engine, text
from core.config import settings

engine = create_engine(settings.DATABASE_URL)


def main():
    with engine.connect() as conn:
        for col_name, col_ddl in [
            ("compose_file_content", "ALTER TABLE agent_deploy_tasks ADD COLUMN compose_file_content TEXT COMMENT 'docker-compose.yml 自定义内容'"),
            ("config_file_content", "ALTER TABLE agent_deploy_tasks ADD COLUMN config_file_content TEXT COMMENT 'config.yaml 自定义内容'"),
        ]:
            row = conn.execute(text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agent_deploy_tasks' "
                "AND COLUMN_NAME = '%s'" % col_name
            )).fetchone()
            if not row:
                conn.execute(text(col_ddl))
                print(f"Added {col_name}")
            else:
                print(f"{col_name} already exists")
        conn.commit()

    print("Migration 0017 completed")


main() if __name__ == "__main__" else None
