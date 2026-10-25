"""`pages/errors/<hash12>.md`: one stub per distinct normalized error string (spec 06).

The hash is the one `check()` computes for an observation (spec 03: sha256 of the normalized
string), so a stub's file name is what an observation row already carries.
"""

import hashlib
from collections.abc import Iterable

from apifacts.pages import PagesError
from apifacts.schema.models import Fact, Status

PREFIX_LEN = 12


def error_hash(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalized_of(fact: Fact) -> str | None:
    """The fact's normalized error string, if it has one with any visible text."""
    value = fact.signal.normalized if fact.signal else None
    return value if value and value.strip() else None


def error_groups(facts: Iterable[Fact]) -> dict[str, tuple[str, tuple[Fact, ...]]]:
    """`{hash prefix: (normalized string, facts)}` over non-retracted facts, sorted by prefix, facts
    by id. Two different strings on one prefix stop the build: a stub must name one string."""
    by_string: dict[str, list[Fact]] = {}
    for fact in facts:
        normalized = normalized_of(fact)
        if normalized is not None and fact.status is not Status.retracted:
            by_string.setdefault(normalized, []).append(fact)
    groups: dict[str, tuple[str, tuple[Fact, ...]]] = {}
    for normalized, group in by_string.items():
        prefix = error_hash(normalized)[:PREFIX_LEN]
        if prefix in groups:
            other = groups[prefix][0]
            message = f"error hash prefix collision on {prefix}: {other!r} and {normalized!r}"
            raise PagesError(message)
        groups[prefix] = (normalized, tuple(sorted(group, key=lambda f: f.id)))
    return dict(sorted(groups.items()))
