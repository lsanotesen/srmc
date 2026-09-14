#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=== 编译 srmc-agent 静态二进制文件 ==="
echo ""

# 检查 Go 是否安装
if ! command -v go &> /dev/null; then
    echo "错误: 未安装 Go，请先安装 Go 1.22+"
    echo "安装方式: https://go.dev/doc/install"
    exit 1
fi

# 显示 Go 版本
echo "Go 版本: $(go version)"
echo ""

# 创建输出目录
mkdir -p output

# 编译参数
BUILD_FLAGS="-s -w"  # 去除调试信息，减小体积
BUILD_TAGS="purego"  # 使用纯 Go 实现，避免 CGO

echo "正在编译..."
echo "  CGO_ENABLED=0"
echo "  go build -tags ${BUILD_TAGS} -ldflags='${BUILD_FLAGS}'"
echo ""

# 静态编译 Linux amd64
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -tags "${BUILD_TAGS}" \
    -ldflags="${BUILD_FLAGS}" \
    -o output/srmc-agent-linux-amd64 \
    .

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 编译成功！"
    echo ""
    
    # 显示文件信息
    echo "文件信息:"
    ls -lh output/srmc-agent-linux-amd64
    echo ""
    
    # 检查是否为静态链接
    if file output/srmc-agent-linux-amd64 | grep -q "statically linked"; then
        echo "✅ 确认: 静态链接二进制文件（无 GLIBC 依赖）"
    else
        echo "⚠️  警告: 可能仍有动态链接依赖"
        file output/srmc-agent-linux-amd64
        echo "检查依赖:"
        ldd output/srmc-agent-linux-amd64 2>/dev/null || echo "  (ldd 不可用或无依赖)"
    fi
    
    echo ""
    echo "=== 部署说明 ==="
    echo "1. 将二进制文件复制到目标服务器:"
    echo "   scp output/srmc-agent-linux-amd64 user@server:/usr/local/bin/srmc-agent"
    echo ""
    echo "2. 在目标服务器上执行:"
    echo "   chmod +x /usr/local/bin/srmc-agent"
    echo "   systemctl restart srmc-agent"
    echo ""
else
    echo "❌ 编译失败！"
    exit 1
fi
