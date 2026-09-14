#!/bin/bash

echo "Waiting for MySQL to be ready..."
sleep 10

echo "Initializing admin user..."
python init_sql/init_admin.py

echo "Running database migrations..."
python -m migrations.0013_add_agent_deploy_meta || true
python -m migrations.0014_create_agent_deploy_tables || true
python -m migrations.0015_extend_audit_action_enum || true
python -m migrations.0016_add_update_task_extra_files || true
python -m migrations.0017_add_deploy_task_extra_files || true
python -m migrations.0018_add_server_org_isolation || true

echo "Starting FastAPI server with HTTP/2..."
# --http httptools: 使用高性能 HTTP 解析器
# HTTP/2 由浏览器自动协商，无需额外配置
# 关键：如果前面有 Nginx，需确保 Nginx 启用了 HTTP/2
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --http httptools