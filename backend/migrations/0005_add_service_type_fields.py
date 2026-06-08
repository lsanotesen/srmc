"""Migration to add service type and deployment fields"""
from sqlalchemy import text
from core.database import engine

def upgrade():
    """Add new fields to app_services table for service type enhancement"""
    with engine.begin() as conn:
        # 创建枚举类型
        conn.execute(text("""
            CREATE TYPE service_type AS ENUM (
                'HOST_APP', 'DOCKER', 'ES', 'SOLR', 'REDIS', 'MYSQL', 
                'POSTGRESQL', 'KAFKA', 'ROCKETMQ', 'RABBITMQ', 'NGINX', 'AI_MODEL'
            )
        """))
        
        conn.execute(text("""
            CREATE TYPE deploy_type AS ENUM ('HOST', 'DOCKER', 'CLUSTER')
        """))
        
        # 添加新字段
        conn.execute(text("ALTER TABLE app_services ADD COLUMN service_type service_type DEFAULT 'HOST_APP'"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN deploy_type deploy_type DEFAULT 'HOST'"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN instance_name VARCHAR(255)"))
        
        # Docker相关字段
        conn.execute(text("ALTER TABLE app_services ADD COLUMN container_name VARCHAR(255)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN image_name VARCHAR(255)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN image_tag VARCHAR(100)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN container_id VARCHAR(64)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN port_mapping VARCHAR(500)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN volume_mapping VARCHAR(1000)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN network_mode VARCHAR(100)"))
        
        # 集群相关字段
        conn.execute(text("ALTER TABLE app_services ADD COLUMN cluster_name VARCHAR(255)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN node_count INTEGER"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN master_node VARCHAR(45)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN data_nodes VARCHAR(500)"))
        
        # Redis相关字段
        conn.execute(text("ALTER TABLE app_services ADD COLUMN redis_role VARCHAR(50)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN redis_memory_usage VARCHAR(50)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN redis_key_count BIGINT"))
        
        # MySQL相关字段
        conn.execute(text("ALTER TABLE app_services ADD COLUMN mysql_version VARCHAR(50)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN mysql_connection_count INTEGER"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN mysql_slave_status VARCHAR(50)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN mysql_db_count INTEGER"))
        
        # 监控状态字段
        conn.execute(text("ALTER TABLE app_services ADD COLUMN status VARCHAR(50) DEFAULT 'stopped'"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN cpu_usage VARCHAR(20)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN memory_usage VARCHAR(20)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN disk_usage VARCHAR(20)"))
        conn.execute(text("ALTER TABLE app_services ADD COLUMN network_io VARCHAR(100)"))
        
        # 修改 program_path 为可空（兼容非HOST_APP类型）
        conn.execute(text("ALTER TABLE app_services ALTER COLUMN program_path DROP NOT NULL"))
        
        print("Migration completed successfully")

def downgrade():
    """Rollback migration"""
    with engine.begin() as conn:
        # 删除新增字段
        fields = [
            'service_type', 'deploy_type', 'instance_name',
            'container_name', 'image_name', 'image_tag', 'container_id',
            'port_mapping', 'volume_mapping', 'network_mode',
            'cluster_name', 'node_count', 'master_node', 'data_nodes',
            'redis_role', 'redis_memory_usage', 'redis_key_count',
            'mysql_version', 'mysql_connection_count', 'mysql_slave_status', 'mysql_db_count',
            'status', 'cpu_usage', 'memory_usage', 'disk_usage', 'network_io'
        ]
        for field in fields:
            conn.execute(text(f"ALTER TABLE app_services DROP COLUMN IF EXISTS {field}"))
        
        # 删除枚举类型
        conn.execute(text("DROP TYPE IF EXISTS service_type"))
        conn.execute(text("DROP TYPE IF EXISTS deploy_type"))
        
        # 恢复 program_path 非空约束
        conn.execute(text("ALTER TABLE app_services ALTER COLUMN program_path SET NOT NULL"))

if __name__ == "__main__":
    upgrade()
