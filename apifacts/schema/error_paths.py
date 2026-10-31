"""Where vendors put the error in a JSON body: one list for the probe runner and check() (D-090).

The runner records a fact's error string through `MESSAGE_PATHS`; check() reads its whitelist
(`signal_fields`) first and these paths only for errors inside a list, which a `signal_fields`
name cannot address. Both sides therefore derive the same string from the same body, and a
report hashes to the fact it is about.
"""

from collections.abc import Iterable
from typing import Any

from apifacts.probe.templating import lookup

# The human-readable error, most specific first.
MESSAGE_PATHS = (
    ".error.message",
    ".error_description",
    ".message",
    ".detail",
    ".error",
    ".errors[0].message",
    ".title",
    ".description",  # Telegram: {ok: false, error_code, description}
    "[0].message",  # Salesforce: [{message, errorCode}]
)
# Vendor error codes inside a list, out of reach of a `signal_fields` name.
CODE_PATHS = (
    ".error.errors[0].reason",  # Google: {error: {code, message, errors: [{domain, reason}]}}
    "[0].errorCode",  # Salesforce
    ".errors[0].extensions.code",  # GraphQL (Apollo, Linear): {errors: [{message, extensions}]}
)
# The message paths that go through a list: the only ones check() takes off its whitelist.
LIST_MESSAGE_PATHS = tuple(p for p in MESSAGE_PATHS if "[" in p)


def first_string(doc: Any, paths: Iterable[str]) -> str | None:
    """The first non-blank string found along `paths` (`.name` / `[index]` segments)."""
    for path in paths:
        try:
            value = lookup(doc, path)
        except LookupError:
            continue
        if isinstance(value, str) and value.strip():
            return value
    return None
