import json
import os
import re
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

YEAR_RE = re.compile(r"[（(](\d{4})[)）]")


def api_get(path):
    req = urllib.request.Request(f"{API_BASE}{path}", headers={"X-Admin-Token": ADMIN_TOKEN})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def api_post(path):
    req = urllib.request.Request(f"{API_BASE}{path}", method="POST", headers={"X-Admin-Token": ADMIN_TOKEN})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def clean_title(t):
    t = re.sub(r"[（(]\d{4}[)）]", "", t)
    t = re.sub(r"[（(].*?[)）]", "", t)
    t = re.sub(r"\s*(4K|1080P|高清|完整版|无删减|国语|粤语|中字).*$", "", t, flags=re.IGNORECASE)
    return t.strip()


conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT id, title FROM resources WHERE category='电影' AND (tmdb_id IS NULL OR tmdb_id='') ORDER BY id")
rows = cur.fetchall()
conn.close()

print(f"共 {len(rows)} 部电影待处理")

matched = 0
unmatched = []
errors = []

limit = None
if "--limit" in sys.argv:
    limit = int(sys.argv[sys.argv.index("--limit") + 1])
    rows = rows[:limit]

for i, (rid, raw_title) in enumerate(rows, start=1):
    m = YEAR_RE.search(raw_title)
    year = int(m.group(1)) if m else None
    title = clean_title(raw_title)
    try:
        q = urllib.parse.quote(title)
        results = api_get(f"/api/tmdb/search?q={q}")
        movie_results = [r for r in results if r["media_type"] == "movie"]
        candidates = movie_results or results
        if not candidates:
            unmatched.append((rid, raw_title))
            continue

        pick = None
        for r in candidates:
            if r["title"] == title and (not year or not r.get("year") or str(year) == str(r["year"])):
                pick = r
                break
        if not pick and year:
            for r in candidates:
                if r.get("year") and abs(int(r["year"]) - year) <= 1:
                    pick = r
                    break
        if not pick:
            for r in candidates:
                if r["title"] == title:
                    pick = r
                    break
        if not pick:
            pick = candidates[0]

        api_post(f"/api/tmdb/enrich/{rid}?tmdb_id={pick['tmdb_id']}&media_type={pick['media_type']}")
        matched += 1
    except Exception as e:
        errors.append((rid, raw_title, str(e)))

    if i % 100 == 0:
        print(f"进度 {i}/{len(rows)}  已匹配={matched}  未匹配={len(unmatched)}  错误={len(errors)}")

    time.sleep(DELAY)

print("\n=== 完成 ===")
print(f"总数: {len(rows)}  已匹配补全: {matched}  未匹配: {len(unmatched)}  错误: {len(errors)}")

with open("enrich_movies_unmatched.json", "w", encoding="utf-8") as f:
    json.dump({"unmatched": unmatched, "errors": errors}, f, ensure_ascii=False, indent=2)
