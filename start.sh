#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== 启动影视资源搜索系统 ==="

# 后端
echo "[1/2] 启动后端..."
cd "$ROOT/backend"
nohup venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/movie-search-backend.log 2>&1 &
echo "  后端 PID: $! (http://localhost:8000)"

sleep 2

# 前端
echo "[2/2] 启动前端..."
cd "$ROOT/frontend"
nohup npm run dev > /tmp/movie-search-frontend.log 2>&1 &
echo "  前端 PID: $! (http://localhost:3000)"

echo ""
echo "✓ 系统启动完成"
echo "  首页: http://localhost:3000"
echo "  API:  http://localhost:8000/docs"
echo ""
echo "日志: tail -f /tmp/movie-search-backend.log"
echo "日志: tail -f /tmp/movie-search-frontend.log"
