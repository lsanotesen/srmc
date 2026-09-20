#!/bin/bash
set -e
VERSION=latest
IMAGE_NAME="srmc-agent:$VERSION"
OUTPUT_FILE="srmc-agent.tar"

echo "=========================================="
echo "  SRMC Agent Docker 部署脚本"
echo "=========================================="

# 1. 构建镜像
echo ""
echo "[1/2] 构建 Docker 镜像..."
docker build -t $IMAGE_NAME .
echo "构建完成"

# 2. 导出镜像
echo ""
echo "[2/2] 导出镜像到 $OUTPUT_FILE..."
docker save $IMAGE_NAME > $OUTPUT_FILE
echo "导出完成: $(ls -lh $OUTPUT_FILE | awk '{print $5}')"
