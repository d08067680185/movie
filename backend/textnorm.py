"""关键词归一化：search.py（SearchLog热词统计）和 livesearch.py（PanSou缓存key）
共用，避免"三体"和"三体 "（尾部空格）/大小写不同的英文标题被当成不同key。"""
import re


def normalize_keyword(keyword: str) -> str:
    """大小写不敏感(casefold，比lower()更彻底) + 折叠连续空白(含全角空格)为单个空格。
    不做更激进的处理(如去标点)，避免影响真实语义不同的关键词。"""
    k = keyword.strip().casefold()
    k = re.sub(r"[\s　]+", " ", k)
    return k
