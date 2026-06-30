#!/bin/bash
echo "=== 停止影视资源搜索系统 ==="
pkill -f "uvicorn main:app" 2>/dev/null && echo "  后端已停止" || echo "  后端未运行"
pkill -f "next dev"         2>/dev/null && echo "  前端(dev)已停止"  || true
pkill -f "next start"       2>/dev/null && echo "  前端(prod)已停止" || true
echo "完成"
