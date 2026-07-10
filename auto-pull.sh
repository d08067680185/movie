#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

REPO_DIR="/Users/xiaofengdai/Documents/claude/movie"
LOG_FILE="$REPO_DIR/auto-pull.log"
LOCAL_PORT=8092
DB="backend/movie_search.db"

cd "$REPO_DIR"

if ! git fetch origin main >> "$LOG_FILE" 2>&1; then
    "$HOME/bin/kids-alert.sh" movie-fetch "movie git fetch 失败（认证或网络断链）" "$(tail -3 \"$LOG_FILE\")"
    exit 1
fi

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 检测到新提交，开始更新 ($LOCAL -> $REMOTE)..." >> "$LOG_FILE"

CHANGED=$(git diff --name-only "$LOCAL" "$REMOTE" 2>/dev/null || true)

# ── 远端更新了数据库：容器在写这个文件（WAL 模式），直接 pull 会失败或损坏库。
# 安全替换流程：先构建 → 停后端（干净关库）→ 备份本地库 → 丢弃本地改动接收远端 → 清 WAL 残留 → 重启。
# 本地累积的 view_count 会被远端库覆盖（开发机部署前有回同步脚本），备份保底。
if echo "$CHANGED" | grep -qx "$DB"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 远端包含数据库更新，进入安全替换流程..." >> "$LOG_FILE"

    # 1) 先构建，失败则放弃且不影响运行中的容器
    if ! docker compose build >> "$LOG_FILE" 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ 构建失败，放弃本次更新，旧容器继续运行" >> "$LOG_FILE"
        osascript -e 'display notification "movie 构建失败，旧版本仍在运行" with title "自动同步告警" sound name "Basso"' 2>/dev/null || true
        "$HOME/bin/kids-alert.sh" movie-build "movie 构建失败（DB 更新流程中）" "$(tail -3 \"$LOG_FILE\")"
        exit 1
    fi

    # 2) 停后端，让 sqlite 干净关闭并 checkpoint WAL
    docker compose stop backend >> "$LOG_FILE" 2>&1

    # 3) 备份当前运行库（保留最近 5 份）
    mkdir -p backend/backups
    TS=$(date +%Y%m%d-%H%M%S)
    cp "$DB" "backend/backups/pre-deploy-$TS.db"
    ls -1t backend/backups/pre-deploy-*.db 2>/dev/null | tail -n +6 | xargs -I{} rm -f {}

    # 4) 丢弃本地对库的改动，以远端为准
    git checkout -- "$DB" >> "$LOG_FILE" 2>&1
    if ! git pull --ff-only origin main >> "$LOG_FILE" 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ pull 仍失败（其他文件冲突？），恢复旧容器运行" >> "$LOG_FILE"
        docker compose up -d >> "$LOG_FILE" 2>&1
        "$HOME/bin/kids-alert.sh" movie-pull "movie DB 替换流程中 pull 失败，需人工处理" "$(tail -5 \"$LOG_FILE\")"
        exit 1
    fi

    # 5) 清掉旧库残留的 WAL/SHM（与新库不配套，留着会损坏数据）
    rm -f "${DB}-wal" "${DB}-shm"

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 数据库已更新（本地库备份为 pre-deploy-$TS.db），重启容器..." >> "$LOG_FILE"
    docker compose up -d >> "$LOG_FILE" 2>&1

else
    # ── 常规路径：远端不动数据库，本地脏的 db 不影响 ff-only pull
    if ! git pull --ff-only origin main >> "$LOG_FILE" 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ git pull 失败，跳过本次同步" >> "$LOG_FILE"
        osascript -e 'display notification "movie git pull 失败，请检查工作树" with title "自动同步告警" sound name "Basso"' 2>/dev/null || true
        "$HOME/bin/kids-alert.sh" movie-pull "movie git pull 失败（工作树脏或分叉）" "$(tail -3 \"$LOG_FILE\")"
        exit 1
    fi

    if ! echo "$CHANGED" | grep -qvE '\.(md|txt)$'; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 仅文档变更，跳过重建" >> "$LOG_FILE"
        exit 0
    fi

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 重建镜像..." >> "$LOG_FILE"
    if ! docker compose build >> "$LOG_FILE" 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ docker compose build 失败，保持旧容器运行" >> "$LOG_FILE"
        osascript -e 'display notification "movie 构建失败，旧版本仍在运行，请检查 auto-pull.log" with title "自动同步告警" sound name "Basso"' 2>/dev/null || true
        exit 1
    fi

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 重启容器..." >> "$LOG_FILE"
    docker compose up -d >> "$LOG_FILE" 2>&1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 等待容器健康..." >> "$LOG_FILE"
for i in $(seq 1 30); do
    sleep 2
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 4 "http://127.0.0.1:${LOCAL_PORT}/api/stats" 2>/dev/null)
    if [ "$code" = "200" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 更新完成，服务健康 (用时 $((i*2))s)" >> "$LOG_FILE"
        exit 0
    fi
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ 容器启动超时，请检查 docker logs" >> "$LOG_FILE"
osascript -e 'display notification "movie 更新后容器启动超时，请检查 docker logs" with title "自动同步告警" sound name "Basso"' 2>/dev/null || true
exit 1
