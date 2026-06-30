#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-dev}"   # dev | prod

echo "=== 启动影视资源搜索系统 (mode: $MODE) ==="

# 后端
echo "[1/2] 启动后端..."
cd "$ROOT/backend"
if [ ! -d "venv" ]; then
  echo "  初始化 venv..."
  python3 -m venv venv
  venv/bin/pip install -r requirements.txt -q
fi
nohup venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/movie-search-backend.log 2>&1 &
echo "  后端 PID: $! (http://localhost:8000)"

# 前端
echo "[2/2] 启动前端..."
cd "$ROOT/frontend"
if [ ! -d "node_modules" ]; then
  echo "  安装依赖..."
  npm install -q
fi

if [ "$MODE" = "prod" ]; then
  echo "  构建生产版本..."
  npm run build > /tmp/movie-search-build.log 2>&1
  nohup npm start > /tmp/movie-search-frontend.log 2>&1 &
else
  nohup npm run dev > /tmp/movie-search-frontend.log 2>&1 &
fi
echo "  前端 PID: $!"

echo ""
echo "✓ 系统启动完成"
if [ "$MODE" = "prod" ]; then
  echo "  首页: http://$(hostname -I | awk '{print $1}'):3000"
else
  echo "  首页: http://localhost:3000"
fi
echo "  API:  http://localhost:8000/docs"
echo ""
echo "日志: tail -f /tmp/movie-search-backend.log"
echo "日志: tail -f /tmp/movie-search-frontend.log"
