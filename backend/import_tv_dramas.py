import json
import os
import re
import sys
from collections import defaultdict
from urllib.parse import urlsplit, parse_qs
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


SRC_PATH = "/Users/zhuzhu/Desktop/项目资料/flowus_tv_dramas_v3.json"
API_URL = "http://localhost:8000/api/admin/batch-import"
ADMIN_TOKEN = load_admin_token()
BATCH_SIZE = 50

with open(SRC_PATH, encoding="utf-8") as f:
    rows = json.load(f)

for r in rows:
    r["title"] = re.sub(r"\s*打开\s*$", "", r["title"]).strip()

groups = defaultdict(list)
for r in rows:
    groups[r["title"]].append(r)

items = []
for title, group in groups.items():
    years = [g["year"] for g in group if g.get("year") and g["year"].isdigit()]
    year = int(years[0]) if years else None
    genres = [g["genre"] for g in group if g.get("genre")]
    genre = genres[0] if genres else None
    statuses = [g["status"] for g in group if g.get("status")]
    status = statuses[0] if statuses else None
    actors_list = [g["actors"] for g in group if g.get("actors")]
    ep_counts = [g["episodeCount"] for g in group if g.get("episodeCount")]
    synopsis_parts = []
    if actors_list:
        synopsis_parts.append(f"主演：{actors_list[0]}")
    if ep_counts:
        synopsis_parts.append(f"共{ep_counts[0]}集")
    synopsis = "；".join(synopsis_parts) or None

    multi = len(group) > 1
    links = []
    for idx, g in enumerate(group, start=1):
        ep_info = f"第{idx}集" if multi else None
        quark = g.get("quark")
        if quark:
            links.append({
                "url": quark,
                "link_type": "pan_quark",
                "episode_info": ep_info,
                "password": None,
            })
        baidu = g.get("baidu")
        if baidu:
            parts = urlsplit(baidu)
            base_url = f"{parts.scheme}://{parts.netloc}{parts.path}"
            qs = parse_qs(parts.query)
            pwd = (qs.get("pwd") or [None])[0]
            links.append({
                "url": base_url,
                "link_type": "pan_baidu",
                "episode_info": ep_info,
                "password": pwd,
            })

    items.append({
        "title": title,
        "year": year,
        "category": "电视剧",
        "genre": genre,
        "status": status,
        "synopsis": synopsis,
        "links": links,
    })

print(f"共 {len(rows)} 行原始数据，分组为 {len(items)} 部剧目")
print("样例:")
for it in items[:3]:
    print(json.dumps(it, ensure_ascii=False, indent=2))

if "--commit" not in sys.argv:
    print("\n[DRY RUN] 未写入数据库。加 --commit 参数执行真实导入。")
    sys.exit(0)

total = {"created": 0, "updated": 0, "links_added": 0, "skipped": 0, "errors": []}
for i in range(0, len(items), BATCH_SIZE):
    batch = items[i:i + BATCH_SIZE]
    body = json.dumps(batch).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-Admin-Token": ADMIN_TOKEN},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    total["created"] += result["created"]
    total["updated"] += result["updated"]
    total["links_added"] += result["links_added"]
    total["skipped"] += result["skipped"]
    total["errors"].extend(result["errors"])
    print(f"批次 {i // BATCH_SIZE + 1}: created={result['created']} updated={result['updated']} links_added={result['links_added']} skipped={result['skipped']}")

print("\n=== 导入完成 ===")
print(json.dumps(total, ensure_ascii=False, indent=2))
