#!/bin/bash
# 微信公众号自动评论机器人 - 一键打包脚本 (macOS/Linux)
#
# 使用方法：
#   chmod +x build.sh
#   ./build.sh

set -e

echo "=============================================="
echo "微信公众号自动评论机器人 - 一键打包"
echo "=============================================="

# 进入脚本所在目录
cd "$(dirname "$0")"

# 检查 uv 是否安装
if ! command -v uv &> /dev/null; then
    echo "错误: 未找到 uv，请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 同步依赖
echo ""
echo "[1/3] 同步依赖..."
uv sync

# 运行打包脚本
echo ""
echo "[2/3] 开始打包..."
uv run python build.py

echo ""
echo "[3/3] 打包完成！"
echo ""
echo "输出目录: dist/"
echo ""
echo "请将 dist/ 目录压缩后分发给用户。"
