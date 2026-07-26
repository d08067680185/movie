from textnorm import normalize_keyword


def test_normalize_keyword_casefolds():
    assert normalize_keyword("Iron Man") == normalize_keyword("iron man")


def test_normalize_keyword_collapses_whitespace():
    assert normalize_keyword("iron  man") == normalize_keyword("iron man")


def test_normalize_keyword_folds_fullwidth_space():
    assert normalize_keyword("三体　") == normalize_keyword("三体")


def test_normalize_keyword_strips_leading_trailing_whitespace():
    assert normalize_keyword("  三体  ") == "三体"


def test_normalize_keyword_distinguishes_different_words():
    assert normalize_keyword("三体") != normalize_keyword("三体2")
