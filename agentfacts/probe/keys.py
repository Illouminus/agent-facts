"""Probe keys, by name only: `services/<s>.yaml::auth.key_name` → `<keys_dir>/<key_name>.key`.

The runner is the only reader (invariant 4). `key_name` is pattern-checked by the service schema
(`^[a-z0-9][a-z0-9_-]{0,63}$`), so it cannot leave `keys_dir`. A missing or blank file means no key:
the service's keyed probes are skipped, never an error.
"""

from pathlib import Path

DEFAULT_KEYS_DIR = Path.home() / ".private_keys"


def key_path(key_name: str, keys_dir: Path) -> Path:
    return keys_dir / f"{key_name}.key"


def read_key(key_name: str, keys_dir: Path) -> str | None:
    try:
        value = key_path(key_name, keys_dir).read_text(encoding="utf-8").strip()
    except (FileNotFoundError, NotADirectoryError):
        return None
    return value or None


def has_key(key_name: str, keys_dir: Path) -> bool:
    return read_key(key_name, keys_dir) is not None
