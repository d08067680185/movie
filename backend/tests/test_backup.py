import os
import sqlite3

import pytest

from utils import backup_db, _verify_backup_integrity, verify_backup_restorable


def _create_realistic_db(path: str, with_data: bool = True):
    """构造一个带有 resources/resource_links/sources 三张表的最小库，
    匹配 verify_backup_restorable 实际检查的表结构。"""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE resources (id INTEGER PRIMARY KEY, title TEXT)")
    conn.execute("CREATE TABLE resource_links (id INTEGER PRIMARY KEY, resource_id INTEGER, url TEXT)")
    conn.execute("CREATE TABLE sources (id INTEGER PRIMARY KEY, name TEXT)")
    if with_data:
        conn.execute("INSERT INTO resources (title) VALUES ('测试资源')")
    conn.commit()
    conn.close()


def test_verify_backup_integrity_accepts_valid_sqlite_file(tmp_path):
    db_path = tmp_path / "valid.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    assert _verify_backup_integrity(str(db_path)) is True


def test_verify_backup_integrity_rejects_corrupted_file(tmp_path):
    bad_path = tmp_path / "bad.db"
    bad_path.write_bytes(b"this is not a sqlite database" * 50)

    assert _verify_backup_integrity(str(bad_path)) is False


def test_verify_backup_integrity_rejects_missing_file(tmp_path):
    missing_path = tmp_path / "does_not_exist.db"
    assert _verify_backup_integrity(str(missing_path)) is False


def test_backup_db_succeeds_for_valid_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "movie_search.db"
    _create_realistic_db(str(src), with_data=True)

    dest = backup_db(str(src))
    assert dest is not None
    assert os.path.exists(dest)


def test_verify_backup_restorable_passes_with_data(tmp_path):
    db_path = tmp_path / "ok.db"
    _create_realistic_db(str(db_path), with_data=True)

    ok, detail = verify_backup_restorable(str(db_path))
    assert ok is True
    assert "resources" in detail


def test_verify_backup_restorable_fails_when_resources_empty(tmp_path):
    db_path = tmp_path / "empty.db"
    _create_realistic_db(str(db_path), with_data=False)

    ok, detail = verify_backup_restorable(str(db_path))
    assert ok is False


def test_verify_backup_restorable_fails_when_table_missing(tmp_path):
    db_path = tmp_path / "missing_table.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    ok, detail = verify_backup_restorable(str(db_path))
    assert ok is False


def test_backup_db_returns_none_when_restore_drill_fails(tmp_path, monkeypatch):
    """备份文件结构完整(能过integrity_check)但关键表是空的这种情况，
    也应该被判定为坏备份——不只是校验文件没损坏，还要校验真有数据。"""
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "movie_search.db"
    _create_realistic_db(str(src), with_data=False)

    dest = backup_db(str(src))
    assert dest is None
    backup_dir = tmp_path / "backups"
    if backup_dir.exists():
        assert list(backup_dir.iterdir()) == []


def test_backup_db_returns_none_and_cleans_up_on_corrupted_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "movie_search.db"
    src.write_bytes(b"garbage, not a real db" * 50)

    dest = backup_db(str(src))
    assert dest is None
    # 坏备份文件应该被清理掉，不应该残留在 backups/ 目录里
    backup_dir = tmp_path / "backups"
    if backup_dir.exists():
        assert list(backup_dir.iterdir()) == []
