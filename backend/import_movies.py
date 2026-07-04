import json
import os
import sys
from collections import defaultdict
import urllib.request

import openpyxl

SRC_PATH = "/Users/zhuzhu/Desktop/项目资料/电影.xlsx"
API_URL = "http://localhost:8000/api/admin/batch-import"
BATCH_SIZE = 50


def load_admin_token():
    token = os.environ.get("ADMIN_PASSWORD")
    if token:
        return token
    if os.path.exists(".env"):
        for line in open(".env"):
            if line.startswith("ADMIN_PASSWORD="):
                return line.strip().split("=", 1)[1]
    raise SystemExit("ADMIN_PASSWORD not set (env var or backend/.env)")


ADMIN_TOKEN = load_admin_token()

wb = openpyxl.load_workbook(SRC_PATH, data_only=True)
ws = wb.active
rows = list(ws.iter_rows(min_row=2, values_only=True))

groups = defaultdict(list)
for r in rows:
    title, quark = r[1], r[2]
    if not title or not quark:
        continue
    title = str(title).strip()
    groups[title].append(quark.strip())

items = []
for title, links in groups.items():
    unique_links = list(dict.fromkeys(links))
    multi = len(unique_links) > 1
    item_links = []
    for idx, url in enumerate(unique_links, start=1):
        item_links.append({
            "url": url,
            "link_type": "pan_quark",
            "episode_info": f"资源{idx}" if multi else None,
            "password": None,
        })
    items.append({
        "title": title,
        "category": "电影",
        "links": item_links,
    })

print(f"共 {len(rows)} 行原始数据，分组为 {len(items)} 部电影")
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
