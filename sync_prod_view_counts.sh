#!/bin/bash
# 部署前先跑这个：把生产库当前的 view_count 同步回本地，
# 避免 git checkout + pull 用本地(通常是0)的访问量覆盖掉生产真实积累的访问量。
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROD_HOST="xiaofengdai@100.85.130.18"
PROD_DIR="~/Documents/claude/movie/backend"

echo "拉取生产库 view_count..."
ssh "$PROD_HOST" "cd $PROD_DIR && sqlite3 -json movie_search.db \"SELECT id, view_count FROM resources WHERE view_count > 0;\"" > /tmp/prod_view_counts.json

python3 -c "
import sqlite3, json
data = json.load(open('/tmp/prod_view_counts.json'))
conn = sqlite3.connect('$ROOT/backend/movie_search.db')
cur = conn.cursor()
updated = 0
for row in data:
    cur.execute('UPDATE resources SET view_count=? WHERE id=? AND view_count < ?', (row['view_count'], row['id'], row['view_count']))
    if cur.rowcount:
        updated += 1
conn.commit()
print(f'已同步 {updated} 条 view_count 到本地')
"
rm -f /tmp/prod_view_counts.json
echo "完成。现在可以正常 git add/commit/push，再部署到生产。"
