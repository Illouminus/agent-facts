"""Keys are read by name from `<keys_dir>/<key_name>.key`, only by the runner (spec 04)."""

from agentfacts.probe.keys import DEFAULT_KEYS_DIR, has_key, read_key


def test_default_dir_is_private_keys_in_home(monkeypatch, tmp_path):
    assert DEFAULT_KEYS_DIR.name == ".private_keys"


def test_reads_and_strips(tmp_path):
    (tmp_path / "svc-test.key").write_text("  value-123\n", encoding="utf-8")
    assert read_key("svc-test", tmp_path) == "value-123"
    assert has_key("svc-test", tmp_path)


def test_missing_file_is_none(tmp_path):
    assert read_key("absent", tmp_path) is None
    assert not has_key("absent", tmp_path)


def test_whitespace_only_file_is_missing(tmp_path):
    (tmp_path / "blank.key").write_text(" \n", encoding="utf-8")
    assert read_key("blank", tmp_path) is None
    assert not has_key("blank", tmp_path)


def test_missing_dir_is_none(tmp_path):
    assert read_key("svc", tmp_path / "nope") is None
