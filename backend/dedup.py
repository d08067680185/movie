"""标题模糊查重共用逻辑，从 find_duplicates.py 抽取而来。"""
import re
from collections import defaultdict

QUALITY_WORDS = r"4K|1080P|1080p|720p|720P|高清|完整版|无删减|国语|粤语|中字|中英双字|修复版|数字修复|蓝光|HD|BD|杜比|导演剪辑版|加长版|未删减版"


def clean_key(title: str) -> str:
    """去掉画质/版本/季数等标签+标点空格，只留下用来判断"是不是同一部作品"的核心字符。"""
    t = title
    t = re.sub(r"[（(【\[][^)）\]】]*[)）\]】]", "", t)
    t = re.sub(QUALITY_WORDS, "", t, flags=re.IGNORECASE)
    t = re.sub(r"第[0-9一二三四五六七八九十]+[季部]", "", t)
    t = re.sub(r"(全)?(系列合集|系列|合集|全集|三部曲|四部曲|双部曲)$", "", t)
    t = re.sub(r"[0-9]+[-~][0-9]+\s*[部季]?$", "", t)
    t = re.sub(r"[0-9]+\s*[部季全]$", "", t)
    t = re.sub(r"[\s.\-_·,，、]+", "", t)
    return t.strip()


def group_fuzzy_duplicates(resources: list[dict]) -> list[dict]:
    """resources: [{id, title, year, ...}]。按 (clean_key(title), year) 分组，
    year 缺失时退化为仅按 clean_key(title) 分组——即两条都缺年份、标题清洗后
    相同的记录仍会被视为候选重复(这是模糊查重的核心价值)，但有年份的和没
    年份的不会互相匹配，避免过度激进。返回 [{key, year, resources}]，只含
    组内 >1 条的分组，按组大小降序。"""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in resources:
        key = clean_key(r["title"] or "")
        if not key:
            continue
        year = r.get("year")
        dict_key = (key, year) if year else (key, None)
        groups[dict_key].append(r)

    result = []
    for (key, year), items in groups.items():
        if len(items) < 2:
            continue
        result.append({"key": key, "year": year, "resources": items})
    result.sort(key=lambda g: len(g["resources"]), reverse=True)
    return result
