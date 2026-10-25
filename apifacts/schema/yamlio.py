"""YAML loading for registry files: ruamel round-trip (keeps key order and line numbers).

Timestamps stay strings: the schemas describe dates as RFC 3339 text, and a fact must not change
meaning because a YAML library guessed a type.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.constructor import RoundTripConstructor


class _Constructor(RoundTripConstructor):
    pass


_Constructor.add_constructor(
    "tag:yaml.org,2002:timestamp", lambda self, node: self.construct_scalar(node)
)


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.Constructor = _Constructor
    return yaml


def load_yaml(path: Path) -> Any:
    """Load one YAML document; raises ruamel's YAMLError on syntax errors or several documents."""
    with path.open(encoding="utf-8") as fh:
        return _yaml().load(fh)


def load_yaml_text(text: str) -> Any:
    """`load_yaml` for text already in memory (e.g. `git show HEAD:<path>`)."""
    return _yaml().load(text)


def plain(data: Any) -> Any:
    """Convert ruamel containers and scalar subclasses to plain JSON-compatible Python values."""
    if isinstance(data, dict):
        return {str(k): plain(v) for k, v in data.items()}
    if isinstance(data, list):
        return [plain(v) for v in data]
    if isinstance(data, bool) or data is None:
        return data
    if isinstance(data, int):
        return int(data)
    if isinstance(data, float):
        return float(data)
    if isinstance(data, str):
        return str(data)
    return data


def line_of(doc: Any, path: Sequence[str | int]) -> int:
    """1-based line of the deepest node on `path` that the document still has (1 if none)."""
    line, node = 0, doc
    for part in path:
        if isinstance(node, CommentedMap) and part in node:
            line = node.lc.key(part)[0]
        elif isinstance(node, CommentedSeq) and isinstance(part, int) and 0 <= part < len(node):
            line = node.lc.item(part)[0]
        else:
            break
        node = node[part]
    return line + 1
