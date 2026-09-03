#!/bin/bash
# 企业级 AI 应用运营平台（活动运营场景） - 启动脚本
# 用法: bash start.sh [端口号]

PORT=${1:-8000}
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "======================================================"
echo "  企业级 AI 应用运营平台（活动运营场景）"
echo "  后端地址: http://0.0.0.0:$PORT"
echo "  前端页面: http://localhost:$PORT"
echo "  API 文档: http://localhost:$PORT/api/stats"
echo "======================================================"
echo ""
echo "  目录结构:"
echo "    $DIR/main.py        ← Flask 后端"
echo "    $DIR/database.py    ← 数据库模块"
echo "    $DIR/static/        ← 前端页面"
echo "    $DIR/sop_platform.db ← SQLite 数据库（自动创建）"
echo ""
echo "  Ctrl+C 停止服务"
echo "======================================================"

python main.py
