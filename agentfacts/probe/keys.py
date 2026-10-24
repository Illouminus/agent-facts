"""Probe keys, by name only: `services/<s>.yaml::auth.key_name` → `<keys_dir>/<key_name>.key`.

The runner is the only reader (invariant 4). `key_name` is pattern-checked by the service schema
(`^[a-z0-9][a-z0-9_-]{0,63}$`), so it cannot leave `keys_dir`. A missing or blank file means no key:
the service's keyed probes are skipped, never an error.

A key is bound to its service by name (`key_bound_to_service`: `stripe-test` for `stripe`), or is
a vendor family key (`google-api-key` for `google-sheets`) whose services list only the family's
API hosts and scopes (`registry.KEY_FAMILIES`); the validator rejects any other name in CI and
the runner refuses it again at run time, key unread.
`has_key` only looks at the file (dry runs and `probe list` never read a value).
"""

import stat
from pathlib import Path

DEFAULT_KEYS_DIR = Path.home() / ".private_keys"


def key_path(key_name: str, keys_dir: Path) -> Path:
    return keys_dir / f"{key_name}.key"


def read_key(key_name: str, keys_dir: Path) -> str | None:
    """The key's value, or None when the file is missing, unreadable, not text or blank."""
    try:
        value = key_path(key_name, keys_dir).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return value or None


def has_key(key_name: str, keys_dir: Path) -> bool:
    """A non-empty key file exists; its content is not read (a blank-but-spaces file passes here and
    is skipped as unreadable when the run reads it)."""
    try:
        info = key_path(key_name, keys_dir).stat()
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode) and info.st_size > 0
