"""The deterministic rules of spec 05: kind inference, claim templates, slugs. Pure functions."""

import re
from collections.abc import Collection, Iterable

from apifacts.schema.models import Kind

MAX_CLAIM = 300  # spec 01
SLUG_WORDS = 6  # spec 05: first 6 words of the normalized error
MAX_SLUG_BASE = 60  # leaves room for a -NN dedup suffix; ids and page paths stay short
RESERVED_SLUGS = frozenset({"index"})  # spec 06: `index` is the service page

_RATE_LIMIT_HEADER = re.compile(r"(?i)^(retry-after|x-?rate-?limit.*|rate-?limit.*)$")
_NOT_SLUG = re.compile(r"[^a-z0-9]+")


def infer_kind(status: int | None, normalized: str | None, headers: Iterable[str] = ()) -> Kind:
    """Spec 05, first rule that applies: 429 or a rate-limit header → rate_limit; 2xx with an
    empty body → silent_behavior; 401/403 → auth_quirk; 410 or `Sunset` → deprecation; else
    error_meaning. Observations carry no headers (spec 03 never stores them), so for the quorum
    `headers` is empty and only the status and the presence of a string decide."""
    names = [h.strip() for h in headers]
    if status == 429 or any(_RATE_LIMIT_HEADER.match(h) for h in names):
        return Kind.rate_limit
    if status is not None and 200 <= status < 300 and not normalized:
        return Kind.silent_behavior
    if status in (401, 403):
        return Kind.auth_quirk
    if status == 410 or any(h.lower() == "sunset" for h in names):
        return Kind.deprecation
    return Kind.error_meaning


_TEMPLATES = {
    Kind.rate_limit: "{head} returns HTTP {status}{with_string}, a rate-limit response.",
    Kind.silent_behavior: "{head} returns HTTP {status} with an empty body.",
    Kind.auth_quirk: "{head} refuses the request with HTTP {status}{with_string}.",
    Kind.deprecation: "{head} returns HTTP {status}{with_string}, a deprecation signal.",
    Kind.error_meaning: "{head} returns HTTP {status}{with_string}.",
}
_NO_STATUS = "{head} fails with \"{string}\"."


def claim_for(
    kind: Kind, method: str, template: str, status: int | None, normalized: str | None
) -> str:
    """One declarative sentence from the kind's template; the error string is the normalized
    one (spec 05: pages render only normalized strings), cut with `…` to fit 300 chars."""
    head = f"{method} {template}"

    def render(string: str | None) -> str:
        if status is None:
            return _NO_STATUS.format(head=head, string=string or "")
        with_string = f' with "{string}"' if string else ""
        return _TEMPLATES[kind].format(head=head, status=status, with_string=with_string)

    claim = render(normalized)
    if len(claim) <= MAX_CLAIM or not normalized:
        return claim[:MAX_CLAIM]
    room = len(normalized) - (len(claim) - MAX_CLAIM) - 1
    return render(normalized[: max(room, 0)].rstrip() + "…")[:MAX_CLAIM]


def slug_base(status: int | None, normalized: str | None) -> str:
    """`{status}-{first 6 words of the normalized error, kebab}` (spec 05); either part may be
    missing. Placeholders keep their word (`<id>` → `id`), digit masks (`###`) vanish."""
    words = []
    for word in (normalized or "").split()[:SLUG_WORDS]:
        if kebab := _NOT_SLUG.sub("-", word.lower()).strip("-"):
            words.append(kebab)
    parts = ([str(status)] if status is not None else []) + words
    base = "-".join(parts)[:MAX_SLUG_BASE].strip("-") or "signal"
    return base


def unique_slug(base: str, taken: Collection[str]) -> str:
    """`base`, else `base-2`, `base-3`, … — the first not in `taken` (nor reserved)."""
    slug, n = base, 1
    while slug in taken or slug in RESERVED_SLUGS:
        n += 1
        slug = f"{base}-{n}"
    return slug
