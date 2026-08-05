from sqlalchemy import create_engine, MetaData, Table, Column, VARCHAR, TEXT, DATETIME, Integer, BIGINT, JSON
from sqlalchemy.sql import func
from core.config import settings

engine = create_engine(settings.DATABASE_URL)
metadata = MetaData()

agents_table = Table(
    'agents',
    metadata,
    Column('id', BIGINT, primary_key=True, autoincrement=True),
    Column('uuid', VARCHAR(64), nullable=False, unique=True, index=True),
    Column('hostname', VARCHAR(128), nullable=False),
    Column('ip', VARCHAR(45), nullable=False),
    Column('os', VARCHAR(64)),
    Column('kernel', VARCHAR(128)),
    Column('arch', VARCHAR(32)),
    Column('cpu_model', VARCHAR(256)),
    Column('cpu_cores', Integer),
    Column('memory_total', BIGINT),
    Column('agent_version', VARCHAR(32)),
    Column('capabilities', JSON),
    Column('tags', JSON),
    Column('status', VARCHAR(32), default='offline'),
    Column('last_heartbeat', DATETIME),
    Column('created_at', DATETIME, default=func.now()),
    Column('updated_at', DATETIME, default=func.now(), onupdate=func.now()),
)

with engine.connect() as conn:
    agents_table.create(conn, checkfirst=True)
    conn.commit()

print("Agent table created successfully")