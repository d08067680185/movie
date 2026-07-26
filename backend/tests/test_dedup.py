from dedup import clean_key, group_fuzzy_duplicates


def test_clean_key_strips_quality_tags():
    assert clean_key("流浪地球2 4K 蓝光 国语中字") == "流浪地球2"


def test_clean_key_strips_punctuation_and_whitespace():
    assert clean_key("三体 . 第一季") == clean_key("三体第一季")
    assert clean_key("三体  第一季") == clean_key("三体，第一季")


def test_clean_key_strips_brackets():
    assert clean_key("流浪地球2【高清修复版】") == "流浪地球2"


def test_group_fuzzy_duplicates_matches_punctuation_variants():
    resources = [
        {"id": 1, "title": "三体.4K.蓝光", "year": 2023},
        {"id": 2, "title": "三体 高清完整版", "year": 2023},
        {"id": 3, "title": "无关的另一部电影", "year": 2023},
    ]
    groups = group_fuzzy_duplicates(resources)
    assert len(groups) == 1
    ids = {r["id"] for r in groups[0]["resources"]}
    assert ids == {1, 2}


def test_group_fuzzy_duplicates_respects_year_when_present():
    resources = [
        {"id": 1, "title": "三体", "year": 2023},
        {"id": 2, "title": "三体", "year": 2020},
    ]
    groups = group_fuzzy_duplicates(resources)
    # 不同年份不应该被视为重复
    assert groups == []


def test_group_fuzzy_duplicates_groups_missing_year_together():
    resources = [
        {"id": 1, "title": "三体", "year": None},
        {"id": 2, "title": "三体.4K", "year": None},
    ]
    groups = group_fuzzy_duplicates(resources)
    assert len(groups) == 1
    assert {r["id"] for r in groups[0]["resources"]} == {1, 2}


def test_group_fuzzy_duplicates_ignores_singletons():
    resources = [{"id": 1, "title": "独一无二的电影", "year": 2024}]
    assert group_fuzzy_duplicates(resources) == []


def test_group_fuzzy_duplicates_skips_empty_title():
    resources = [
        {"id": 1, "title": "", "year": 2024},
        {"id": 2, "title": "", "year": 2024},
    ]
    assert group_fuzzy_duplicates(resources) == []
