import json
import sqlite3
import sys

DB_PATH = "movie_search.db"

with open("dup_merge_groups.json", encoding="utf-8") as f:
    data = json.load(f)

groups = data["merge_groups"]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

merged_count = 0
links_moved = 0
links_deduped = 0
deleted_resources = 0

for key, members in groups:
    ids = [m[0] for m in members]
    placeholders = ",".join("?" * len(ids))

    cur.execute(
        f"SELECT id, poster_url, synopsis, genre, rating, year FROM resources WHERE id IN ({placeholders})",
        ids,
    )
    rows = cur.fetchall()

    def score(row):
        _, poster, synopsis, genre, rating, year = row
        return sum([bool(poster), bool(synopsis), bool(genre), bool(rating), bool(year)])

    rows.sort(key=lambda r: (-score(r), r[0]))
    primary_id = rows[0][0]
    other_ids = [r[0] for r in rows[1:]]

    if not other_ids:
        continue

    cur.execute(f"SELECT url FROM resource_links WHERE resource_id=?", (primary_id,))
    existing_urls = set(r[0] for r in cur.fetchall())

    other_placeholders = ",".join("?" * len(other_ids))
    cur.execute(
        f"SELECT id, url FROM resource_links WHERE resource_id IN ({other_placeholders})",
        other_ids,
    )
    for link_id, url in cur.fetchall():
        if url in existing_urls:
            links_deduped += 1
            continue
        cur.execute("UPDATE resource_links SET resource_id=? WHERE id=?", (primary_id, link_id))
        existing_urls.add(url)
        links_moved += 1

    cur.execute(f"DELETE FROM resources WHERE id IN ({other_placeholders})", other_ids)
    deleted_resources += len(other_ids)
    merged_count += 1

conn.commit()

integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]

print(f"合并组数: {merged_count}")
print(f"迁移链接数: {links_moved}  去重跳过(URL已存在): {links_deduped}")
print(f"删除的冗余资源数: {deleted_resources}")
print(f"完整性检查: {integrity}")

conn.close()
