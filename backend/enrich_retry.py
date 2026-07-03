import json
import os
import re
import sqlite3
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


def clean_title(t):
    t = re.split(r"[/、]", t)[0]
    t = re.sub(r"[（(【].*?[)）】]", "", t)
    t = re.sub(r"[:：].*", "", t)
    t = re.sub(r"第[0-9一二三四五六七八九十]+季", "", t)
    t = re.sub(r"[0-9]+[-~][0-9]+\s*[季部]?", "", t)
    t = re.sub(r"[0-9]+\s*[季部全]", "", t)
    t = re.sub(r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+", "", t)
    t = re.sub(r"(系列合集|系列|合集|全集|特别版|番外篇|大电影|之.+$)", "", t)
    t = re.sub(r"\s*[0-9]+\s*$", "", t)
    t = t.strip()
    return t


with open("enrich_unmatched.json", encoding="utf-8") as f:
    prev = json.load(f)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# --- Part A: retry unmatched with cleaned titles ---
still_unmatched = []
newly_matched = 0
collisions = []

for rid, title in prev["unmatched"]:
    cleaned = clean_title(title)
    if not cleaned or cleaned == title:
        still_unmatched.append((rid, title))
        continue
    try:
        q = urllib.parse.quote(cleaned)
        results = api_get(f"/api/tmdb/search?q={q}")
        tv_results = [r for r in results if r["media_type"] == "tv"]
        candidates = tv_results or results
        if not candidates:
            still_unmatched.append((rid, title))
            time.sleep(DELAY)
            continue
        pick = None
        for r in candidates:
            if r["title"] == cleaned:
                pick = r
                break
        if not pick:
            pick = candidates[0]
        api_post(f"/api/tmdb/enrich/{rid}?tmdb_id={pick['tmdb_id']}&media_type={pick['media_type']}")
        newly_matched += 1
        print(f"  匹配: {title!r} -> {cleaned!r} -> {pick['title']} ({pick['year']})")
    except urllib.error.HTTPError as e:
        if e.code == 500:
            collisions.append((rid, title, cleaned))
        else:
            still_unmatched.append((rid, title))
    except Exception:
        still_unmatched.append((rid, title))
    time.sleep(DELAY)

print(f"\n二次匹配成功: {newly_matched}  仍未匹配: {len(still_unmatched)}  新增撞车: {len(collisions)}")

# --- Part B: resolve UNIQUE tmdb_id collisions by copying metadata (without tmdb_id) ---
all_errors = prev["errors"] + [(rid, title, "collision") for rid, title, _ in collisions]
copied = 0
copy_failed = []

for rid, title, *_ in all_errors:
    cleaned = clean_title(title)
    try:
        q = urllib.parse.quote(cleaned or title)
        results = api_get(f"/api/tmdb/search?q={q}")
        tv_results = [r for r in results if r["media_type"] == "tv"]
        candidates = tv_results or results
        if not candidates:
            copy_failed.append((rid, title))
            continue
        pick = candidates[0]
        for r in candidates:
            if r["title"] in (title, cleaned):
                pick = r
                break
        tmdb_id = pick["tmdb_id"]

        cur.execute(
            "SELECT id, poster_url, backdrop_url, synopsis, genre, country, rating, rating_count, directors, actors, title_en, original_title FROM resources WHERE tmdb_id=?",
            (tmdb_id,),
        )
        src = cur.fetchone()
        if not src:
            copy_failed.append((rid, title))
            continue
        (_, poster_url, backdrop_url, synopsis, genre, country, rating, rating_count, directors, actors, title_en, original_title) = src
        cur.execute(
            """UPDATE resources SET poster_url=?, backdrop_url=?, synopsis=?, genre=?, country=?, rating=?, rating_count=?, directors=?, actors=?, title_en=?, original_title=? WHERE id=?""",
            (poster_url, backdrop_url, synopsis, genre, country, rating, rating_count, directors, actors, title_en, original_title, rid),
        )
        copied += 1
        print(f"  复制元数据: {title!r} <- tmdb_id={tmdb_id}")
    except Exception as e:
        copy_failed.append((rid, title))
    time.sleep(DELAY)

conn.commit()
conn.close()

print(f"\n撞车条目补齐元数据: {copied}  仍失败: {len(copy_failed)}")

with open("enrich_retry_result.json", "w", encoding="utf-8") as f:
    json.dump(
        {
            "still_unmatched": still_unmatched,
            "copy_failed": copy_failed,
        },
        f,
        ensure_ascii=False,
        indent=2,
    )
