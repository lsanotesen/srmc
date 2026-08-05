#!/bin/bash
# deploy.sh - 构建并导出 Agent Docker 镜像
#
# 用法:
#   ./deploy.sh                    # 构建并导出
#   ./deploy.sh --upload user@host /path  # 构建并上传到目标服务器

set -e

IMAGE_NAME="srmc-agent:latest"
OUTPUT_FILE="srmc-agent.tar"

echo "=========================================="
echo "  SRMC Agent Docker 部署脚本"
echo "=========================================="

# 1. 构建镜像
echo ""
echo "[1/3] 构建 Docker 镜像..."
docker build -t $IMAGE_NAME .
echo "✅ 构建完成"

# 2. 导出镜像
echo ""
echo "[2/3] 导出镜像到 $OUTPUT_FILE..."
docker save $IMAGE_NAME > $OUTPUT_FILE
echo "✅ 导出完成: $(ls -lh $OUTPUT_FILE | awk '{print $5}')"

# 3. 如果指定了上传目标
if [ "$1" = "--upload" ] && [ -n "$2" ] && [ -n "$3" ]; then
    REMOTE_HOST="$2"
    REMOTE_PATH="$3"

    echo ""
    echo "[3/3] 上传到 $REMOTE_HOST:$REMOTE_PATH..."

    # 创建远程目录并上传必要文件
    ssh $REMOTE_HOST "mkdir -p $REMOTE_PATH/srmc-agent"

    # 上传镜像
    scp $OUTPUT_FILE $REMOTE_HOST:$REMOTE_PATH/srmc-agent/

    # 上传配置文件（如果存在）
    if [ -f "docker-compose.yml" ]; then
        scp docker-compose.yml $REMOTE_HOST:$REMOTE_PATH/srmc-agent/
    fi
    if [ -f "config.yaml" ]; then
        scp config.yaml $REMOTE_HOST:$REMOTE_PATH/srmc-agent/
    fi

    echo ""
    echo "=========================================="
    echo "  部署完成！"
    echo "=========================================="
    echo ""
    echo "在目标服务器上执行："
    echo ""
    echo "  cd $REMOTE_PATH/srmc-agent"
    echo "  docker load < $OUTPUT_FILE"
    echo "  docker-compose up -d"
    echo ""
else
    echo ""
    echo "[3/3] 跳过上传（未指定 --upload 参数）"
    echo ""
    echo "手动部署步骤："
    echo ""
    echo "  # 上传文件"
    echo "  scp $OUTPUT_FILE user@target:/path/"
    echo "  scp docker-compose.yml user@target:/path/"
    echo ""
    echo "  # 在目标服务器上"
    echo "  cd /path"
    echo "  docker load < $OUTPUT_FILE"
    echo "  docker-compose up -d"
    echo ""
fi
