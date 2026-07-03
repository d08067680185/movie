import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request


def load_admin_token():
    token = os.environ.get("ADMIN_PASSWORD")
    if token:
        return token
    if os.path.exists(".env"):
        for line in open(".env"):
            if line.startswith("ADMIN_PASSWORD="):
                return line.strip().split("=", 1)[1]
    raise SystemExit("ADMIN_PASSWORD not set (env var or backend/.env)")


API_BASE = "http://localhost:8000"
ADMIN_TOKEN = load_admin_token()
DB_PATH = "movie_search.db"
DELAY = 0.15


def api_get(path):
    req = urllib.request.Request(f"{API_BASE}{path}", headers={"X-Admin-Token": ADMIN_TOKEN})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def api_post(path):
    req = urllib.request.Request(f"{API_BASE}{path}", method="POST", headers={"X-Admin-Token": ADMIN_TOKEN})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT id, title, year FROM resources WHERE category='电视剧' ORDER BY id")
rows = cur.fetchall()
conn.close()

print(f"共 {len(rows)} 部电视剧待处理")

matched = 0
unmatched = []
errors = []

limit = None
if "--limit" in sys.argv:
    limit = int(sys.argv[sys.argv.index("--limit") + 1])
    rows = rows[:limit]

for i, (rid, title, year) in enumerate(rows, start=1):
    try:
        q = urllib.parse.quote(title)
        results = api_get(f"/api/tmdb/search?q={q}")
        tv_results = [r for r in results if r["media_type"] == "tv"]
        candidates = tv_results or results
        if not candidates:
            unmatched.append((rid, title))
            continue

        pick = None
        for r in candidates:
            if r["title"] == title:
                pick = r
                break
        if not pick and year:
            for r in candidates:
                if r.get("year") and abs(int(r["year"]) - year) <= 1:
                    pick = r
                    break
        if not pick:
            pick = candidates[0]

        api_post(f"/api/tmdb/enrich/{rid}?tmdb_id={pick['tmdb_id']}&media_type={pick['media_type']}")
        matched += 1
    except Exception as e:
        errors.append((rid, title, str(e)))

    if i % 50 == 0:
        print(f"进度 {i}/{len(rows)}  已匹配={matched}  未匹配={len(unmatched)}  错误={len(errors)}")

    time.sleep(DELAY)

print("\n=== 完成 ===")
print(f"总数: {len(rows)}  已匹配补全: {matched}  未匹配: {len(unmatched)}  错误: {len(errors)}")

if unmatched:
    print("\n未匹配剧目样例(前20):")
    for rid, title in unmatched[:20]:
        print(f"  {rid} {title}")

if errors:
    print("\n错误样例(前20):")
    for rid, title, e in errors[:20]:
        print(f"  {rid} {title}: {e}")

with open("enrich_unmatched.json", "w", encoding="utf-8") as f:
    json.dump({"unmatched": unmatched, "errors": errors}, f, ensure_ascii=False, indent=2)
