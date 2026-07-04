import json
import os
import sqlite3
import time
import urllib.parse
import urllib.request

API_BASE = "http://localhost:8000"
DB_PATH = "movie_search.db"
DELAY = 0.15


def load_admin_token():
    token = os.environ.get("ADMIN_PASSWORD")
    if token:
        return token
    if os.path.exists(".env"):
        for line in open(".env"):
            if line.startswith("ADMIN_PASSWORD="):
                return line.strip().split("=", 1)[1]
    raise SystemExit("ADMIN_PASSWORD not set")


ADMIN_TOKEN = load_admin_token()


def api_get(path):
    req = urllib.request.Request(f"{API_BASE}{path}", headers={"X-Admin-Token": ADMIN_TOKEN})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


with open("dup_merge_groups.json", encoding="utf-8") as f:
    d = json.load(f)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

fixed = 0
left_alone = 0
no_match = 0
already_ok = 0
log = []

for poster, items in d["review_groups"]:
    ids = [i[0] for i in items]
    cur.execute(
        f"SELECT id, title, tmdb_id, poster_url FROM resources WHERE id IN ({','.join('?' * len(ids))})",
        ids,
    )
    rows = cur.fetchall()
    for rid, title, tmdb_id, poster_url in rows:
        if tmdb_id is not None:
            continue  # 有独立确认过的tmdb_id，跳过，视为可信锚点
        try:
            q = urllib.parse.quote(title)
            results = api_get(f"/api/tmdb/search?q={q}")
        except Exception:
            time.sleep(DELAY)
            continue

        exact = [r for r in results if r["title"] == title]
        if not exact:
            no_match += 1
            time.sleep(DELAY)
            continue

        pick = exact[0]
        new_poster = pick.get("poster_url")
        if new_poster == poster_url:
            already_ok += 1
            time.sleep(DELAY)
            continue

        # 精确匹配到了不同的条目 -> 尝试直接指向它
        cur.execute("SELECT id FROM resources WHERE tmdb_id=?", (pick["tmdb_id"],))
        holder = cur.fetchone()
        if holder and holder[0] != rid:
            # 该 tmdb_id 已被别的资源占用，复制其数据(不设tmdb_id，避免唯一约束冲突)
            cur.execute(
                "SELECT poster_url, backdrop_url, synopsis, genre, country, rating, rating_count, "
                "directors, actors, title_en, original_title, duration, year FROM resources WHERE id=?",
                (holder[0],),
            )
            src = cur.fetchone()
            cur.execute(
                "UPDATE resources SET poster_url=?, backdrop_url=?, synopsis=?, genre=?, country=?, "
                "rating=?, rating_count=?, directors=?, actors=?, title_en=?, original_title=?, "
                "duration=?, year=? WHERE id=?",
                (*src, rid),
            )
        else:
            media_type = pick["media_type"]
            try:
                req = urllib.request.Request(
                    f"{API_BASE}/api/tmdb/enrich/{rid}?tmdb_id={pick['tmdb_id']}&media_type={media_type}",
                    method="POST",
                    headers={"X-Admin-Token": ADMIN_TOKEN},
                )
                with urllib.request.urlopen(req):
                    pass
            except Exception as e:
                log.append((rid, title, f"enrich失败: {e}"))
                time.sleep(DELAY)
                continue

        fixed += 1
        log.append((rid, title, f"已修正 poster {poster_url} -> {new_poster}"))
        time.sleep(DELAY)

conn.commit()
integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
conn.close()

print(f"已修正: {fixed}")
print(f"精确匹配但本来就对: {already_ok}")
print(f"重新搜索无精确匹配(保持原样): {no_match}")
print(f"完整性检查: {integrity}")
print()
print("修正样例(前30):")
for rid, title, msg in log[:30]:
    print(f"  {rid} {title}: {msg}")

with open("reverify_log.json", "w", encoding="utf-8") as f:
    json.dump(log, f, ensure_ascii=False, indent=2)
