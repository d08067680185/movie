import os
import sqlite3

import pytest

from utils import backup_db, _verify_backup_integrity


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
    conn = sqlite3.connect(str(src))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    dest = backup_db(str(src))
    assert dest is not None
    assert os.path.exists(dest)


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
