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
python -m migrations.0019_create_agent_update_packages || true
python -m migrations.0020_extend_audit_action_update_package || true
python -m migrations.0021_create_service_container_configs || true
python -m migrations.0022_extend_run_mode_inactive || true

echo "Starting FastAPI server with HTTP/2..."
# --http httptools: 使用高性能 HTTP 解析器
# HTTP/2 由浏览器自动协商，无需额外配置
# 关键：如果前面有 Nginx，需确保 Nginx 启用了 HTTP/2
# 注意：不要加 --reload。reload 的文件监视器会持续扫描整个代码目录，
# 导致每个请求被拖慢到十几秒（实测 /api/projects 15s、/api/services 21s）。
# 开发环境如需热重载，请通过环境变量 UVICORN_RELOAD=1 显式开启。
RELOAD_FLAG=""
if [ "$UVICORN_RELOAD" = "1" ]; then
  RELOAD_FLAG="--reload"
fi
uvicorn main:app --host 0.0.0.0 --port 8000 $RELOAD_FLAG --http httptools