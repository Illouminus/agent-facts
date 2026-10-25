"""Keys are read by name from `<keys_dir>/<key_name>.key`, only by the runner (spec 04)."""

from pathlib import Path

import pytest

from apifacts.probe.keys import DEFAULT_KEYS_DIR, has_key, read_key


def test_default_dir_is_private_keys_in_home():
    assert DEFAULT_KEYS_DIR.name == ".private_keys"


def test_reads_and_strips(tmp_path):
    (tmp_path / "svc-test.key").write_text("  value-123\n", encoding="utf-8")
    assert read_key("svc-test", tmp_path) == "value-123"
    assert has_key("svc-test", tmp_path)


def test_missing_file_is_none(tmp_path):
    assert read_key("absent", tmp_path) is None
    assert not has_key("absent", tmp_path)


def test_whitespace_only_file_is_missing_when_read(tmp_path):
    (tmp_path / "blank.key").write_text(" \n", encoding="utf-8")
    assert read_key("blank", tmp_path) is None


def test_has_key_never_reads_the_value(tmp_path, monkeypatch):
    (tmp_path / "svc.key").write_text("value-123", encoding="utf-8")
    (tmp_path / "empty.key").write_text("", encoding="utf-8")

    def no_read(*args, **kwargs):
        raise AssertionError("has_key read the key")

    monkeypatch.setattr(Path, "read_text", no_read)
    monkeypatch.setattr(Path, "read_bytes", no_read)
    monkeypatch.setattr(Path, "open", no_read)
    assert has_key("svc", tmp_path)
    assert not has_key("empty", tmp_path)
    assert not has_key("absent", tmp_path)


@pytest.mark.parametrize("make", ["directory", "binary", "unreadable"])
def test_unreadable_key_is_missing_not_an_error(tmp_path, make):
    path = tmp_path / "svc.key"
    if make == "directory":
        path.mkdir()
    elif make == "binary":
        path.write_bytes(b"\xff\xfe\x00")
    else:
        path.write_text("value", encoding="utf-8")
        path.chmod(0)
    try:
        assert read_key("svc", tmp_path) is None
    finally:
        path.chmod(0o700)


def test_missing_dir_is_none(tmp_path):
    assert read_key("svc", tmp_path / "nope") is None
