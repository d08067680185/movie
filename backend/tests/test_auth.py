import time
import pytest
from fastapi import HTTPException
import auth


def test_hash_password_roundtrip():
    h = auth.hash_password("mySecret123")
    assert h != "mySecret123"
    assert auth.verify_password("mySecret123", h)
    assert not auth.verify_password("wrong", h)


def test_verify_password_rejects_garbage_hash():
    assert not auth.verify_password("anything", "not-a-bcrypt-hash")


def test_migrate_plaintext_password_clears_plaintext(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text("ADMIN_PASSWORD=legacy_plain\nOTHER=keep\n")

    class FakeSettings:
        ADMIN_PASSWORD = "legacy_plain"
        ADMIN_PASSWORD_HASH = None

    settings = FakeSettings()
    auth.migrate_plaintext_password(settings)

    assert settings.ADMIN_PASSWORD is None
    assert auth.verify_password("legacy_plain", settings.ADMIN_PASSWORD_HASH)
    content = env_file.read_text()
    assert "ADMIN_PASSWORD=" not in content
    assert "ADMIN_PASSWORD_HASH=" in content
    assert "OTHER=keep" in content


def test_migrate_is_noop_when_hash_already_present():
    class FakeSettings:
        ADMIN_PASSWORD = "whatever"
        ADMIN_PASSWORD_HASH = "existing_hash"

    settings = FakeSettings()
    auth.migrate_plaintext_password(settings)
    assert settings.ADMIN_PASSWORD_HASH == "existing_hash"


def test_rate_limit_blocks_after_threshold():
    ip = f"test-ip-{time.time()}"
    for _ in range(auth.MAX_ATTEMPTS):
        auth.check_rate_limit(ip)  # should not raise yet
        auth.record_failure(ip)
    with pytest.raises(HTTPException) as exc:
        auth.check_rate_limit(ip)
    assert exc.value.status_code == 429


def test_rate_limit_resets_on_success():
    ip = f"test-ip-success-{time.time()}"
    for _ in range(auth.MAX_ATTEMPTS - 1):
        auth.record_failure(ip)
    auth.record_success(ip)
    auth.check_rate_limit(ip)  # should not raise, counter was reset
