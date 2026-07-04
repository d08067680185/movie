import re
import sqlite3
from collections import defaultdict

DB_PATH = "movie_search.db"

QUALITY_WORDS = r"4K|1080P|1080p|720p|720P|高清|完整版|无删减|国语|粤语|中字|中英双字|修复版|数字修复|蓝光|HD|BD|杜比|导演剪辑版|加长版|未删减版"


def clean_key(title):
    t = title
    t = re.sub(r"[（(【\[][^)）\]】]*[)）\]】]", "", t)
    t = re.sub(QUALITY_WORDS, "", t, flags=re.IGNORECASE)
    t = re.sub(r"第[0-9一二三四五六七八九十]+[季部]", "", t)
    t = re.sub(r"(全)?(系列合集|系列|合集|全集|三部曲|四部曲|双部曲)$", "", t)
    t = re.sub(r"[0-9]+[-~][0-9]+\s*[部季]?$", "", t)
    t = re.sub(r"[0-9]+\s*[部季全]$", "", t)
    t = re.sub(r"[\s.\-_·,，、]+", "", t)
    return t.strip()


conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT id, title, poster_url, category, created_at FROM resources WHERE poster_url IS NOT NULL AND poster_url != ''")
rows = cur.fetchall()

by_poster = defaultdict(list)
for rid, title, poster, category, created_at in rows:
    by_poster[poster].append((rid, title, category, created_at))

merge_groups = []
review_groups = []

for poster, items in by_poster.items():
    if len(items) < 2:
        continue
    keys = defaultdict(list)
    for rid, title, category, created_at in items:
        keys[clean_key(title)].append((rid, title, category, created_at))
    for key, members in keys.items():
        if len(members) >= 2 and key:
            merge_groups.append((key, members))
    # anything left ungrouped (key appears only once within this poster group) but poster shared
    # -> potential wrong-match, collect for review only if the poster group as a whole has >1 distinct key
    if len(keys) > 1:
        review_groups.append((poster, items))

print(f"候选合并组(标题清洗后完全一致): {len(merge_groups)}")
total_to_merge = sum(len(m) for _, m in merge_groups)
print(f"涉及资源数: {total_to_merge}  预计合并后减少: {total_to_merge - len(merge_groups)}")

print(f"\n可疑组(同海报但标题清洗后不一致，可能是误匹配): {len(review_groups)}")

conn.close()

import json
with open("dup_merge_groups.json", "w", encoding="utf-8") as f:
    json.dump({"merge_groups": merge_groups, "review_groups": review_groups}, f, ensure_ascii=False, indent=2)

print("\n合并组样例(前10):")
for key, members in merge_groups[:10]:
    titles = [m[1] for m in members]
    print(f"  [{key}] {len(members)}条: {titles}")

print("\n可疑组样例(前10):")
for poster, items in review_groups[:10]:
    titles = [i[1] for i in items]
    print(f"  {titles}")
