from sqlalchemy import create_engine, MetaData, Table, Column, BIGINT, ForeignKey, String, JSON, Integer, text
from sqlalchemy.sql import func
from sqlalchemy import inspect
from core.config import settings

engine = create_engine(settings.DATABASE_URL)
metadata = MetaData()

app_services = Table(
    'app_services',
    metadata,
    autoload_with=engine
)

with engine.connect() as conn:
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('app_services')]
    
    if 'agent_uuid' not in columns:
        conn.execute(text("ALTER TABLE app_services ADD COLUMN agent_uuid VARCHAR(64)"))
        conn.execute(text("CREATE INDEX idx_app_services_agent_uuid ON app_services(agent_uuid)"))
        print("Added agent_uuid column to app_services")
    else:
        print("agent_uuid column already exists")
    
    if 'health_url' not in columns:
        conn.execute(text("ALTER TABLE app_services ADD COLUMN health_url VARCHAR(500)"))
        print("Added health_url column to app_services")
    else:
        print("health_url column already exists")
    
    if 'pid_file' not in columns:
        conn.execute(text("ALTER TABLE app_services ADD COLUMN pid_file VARCHAR(500)"))
        print("Added pid_file column to app_services")
    else:
        print("pid_file column already exists")
    
    conn.commit()

print("Migration completed")