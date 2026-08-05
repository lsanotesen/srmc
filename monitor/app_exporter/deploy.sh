#!/bin/bash
# 部署App Exporter到目标服务器

# 配置
TARGET_SERVERS=(
  # 添加目标服务器IP
  # "192.168.1.2"
  # "192.168.1.3"
)

# 监控的应用配置 (格式: app_name:port)
MONITOR_APPS="backend:8000,frontend:5173"

# 监控的Docker容器
MONITOR_DOCKER_CONTAINERS="srmc-backend,srmc-frontend"

# 获取本机IP
LOCAL_IP=$(hostname -I | awk '{print $1}')

echo "开始部署App Exporter..."
echo "本机IP: $LOCAL_IP"
echo "监控应用: $MONITOR_APPS"
echo "监控容器: $MONITOR_DOCKER_CONTAINERS"

# 构建Docker镜像
echo "构建Docker镜像..."
cd /home/isi/srmc/monitor/app_exporter
docker build -t srmc-app-exporter:latest .

# 部署到每台服务器
for server in "${TARGET_SERVERS[@]}"; do
  echo "部署到服务器: $server"
  
  # 复制镜像到目标服务器
  docker save srmc-app-exporter:latest | ssh root@$server "docker load"
  
  # 启动容器
  ssh root@$server "docker run -d \
    --name srmc-app-exporter \
    --restart unless-stopped \
    --network host \
    -e MONITOR_APPS='$MONITOR_APPS' \
    -e MONITOR_DOCKER_CONTAINERS='$MONITOR_DOCKER_CONTAINERS' \
    -e LOCAL_IP='$server' \
    srmc-app-exporter:latest"
  
  echo "部署完成: $server"
done

echo "所有服务器部署完成！"
echo "请更新Prometheus配置以采集这些服务器的指标"