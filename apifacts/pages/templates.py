"""Markdown for every page type in `pages/` (docs/specs/06-pages.md).

Pure functions of already-decided data: `build.py` chooses what is published and passes it in.
Registry text reaches a page in two ways only: normalized error strings inside code spans, and
everything else through `md_text`, so nothing in a YAML file can become a link, HTML or a heading.
"""

import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from urllib.parse import urlsplit

from apifacts.fixes.templates import render_fix
from apifacts.pages import sdk
from apifacts.pages.errors_index import error_hash, normalized_of
from apifacts.pages.example import example
from apifacts.probe.http import INVALID_KEY
from apifacts.schema.models import VERIFIED_STATUSES, Fact, Kind, Probe, Service, Status, Surface

_INLINE = re.compile(r"[\\`*\[\]<>|$~]|(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])")
_BLOCK_START = re.compile(r"^(?:[#+=-]|\d+[.)])")


def _one_line(text: str) -> str:
    return " ".join(text.split())


def code_span(text: str) -> str:
    """`text` as one inline code span, whatever backticks it contains (CommonMark fences)."""
    text = _one_line(text)
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * (longest + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def md_text(text: str) -> str:
    """Plain text that renders as itself: inline markup and block starts are escaped."""
    text = _INLINE.sub(lambda m: "\\" + m.group(0), _one_line(text))
    if lead := _BLOCK_START.match(text):
        end = lead.end()
        text = text[: end - 1] + "\\" + text[end - 1 :]
    return text


def autolink(url: str) -> str:
    """An `<https://…>` autolink; characters an autolink cannot hold are percent-encoded."""
    safe = "".join(
        f"%{ord(c):02X}" if c in "<> " or ord(c) < 0x20 or ord(c) == 0x7F else c for c in url
    )
    return f"<{safe}>"


# ── page data ────────────────────────────────────────────────────────────────────────────────────

CHECK_URL = "https://apifacts.dev/v0/check"
GENERATED_MARK = "This page is generated; edit the YAML, not the page."
FOOTER = (
    "Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · "
    + GENERATED_MARK
)

BADGES = {
    Status.verified_server_prod: "✅",
    Status.verified_server_sandbox: "✅",
    Status.verified_client: "✅",
    Status.official: "🔵",
    Status.reported: "🟡",
    Status.stale: "⚪",
    Status.retracted: "⛔",
}
# Root index columns: (header, statuses counted).
STATUS_COLUMNS = (
    ("✅ verified", VERIFIED_STATUSES),
    ("🔵 official", frozenset({Status.official})),
    ("🟡 reported", frozenset({Status.reported})),
    ("⚪ stale", frozenset({Status.stale})),
    ("⛔ retracted", frozenset({Status.retracted})),
)
KIND_TITLES = {
    Kind.error_meaning: "Error meanings",
    Kind.rate_limit: "Rate limits",
    Kind.breaking_change: "Breaking changes",
    Kind.silent_behavior: "Silent behavior",
    Kind.auth_quirk: "Auth quirks",
    Kind.pagination: "Pagination",
    Kind.sandbox_divergence: "Sandbox divergence",
    Kind.deprecation: "Deprecations",
    Kind.availability: "Availability",
    Kind.schema_drift: "Schema drift",
    Kind.latency_profile: "Latency profiles",
}
DIMENSIONS = ("env", "plan", "region", "account_state")


def utc_date(value: str) -> str:
    """`YYYY-MM-DD` of an RFC 3339 timestamp in UTC (fractional seconds of any length allowed)."""
    moment = datetime.fromisoformat(re.sub(r"\.\d+", "", value))
    return moment.astimezone(UTC).date().isoformat()


def slug_of(fact: Fact) -> str:
    return fact.id.split(":", 2)[2]


def badge(status: Status) -> str:
    return f"{BADGES[status]} {status.value}"


def error_string_of(fact: Fact) -> str | None:
    """The vendor's error message as the probe recorded it (redacted by the runner, spec 04), if
    the fact has one with visible text. Quorum drafts never carry one (spec 05: reporters' bodies
    are kept normalized only), so this is never a reporter's raw text."""
    value = fact.signal.error_string if fact.signal else None
    return _one_line(value) if value and value.strip() else None


def heading(fact: Fact) -> str:
    """The page's subject as plain text: the error string verbatim, else the normalized string,
    else the claim."""
    return error_string_of(fact) or normalized_of(fact) or _one_line(fact.claim)


def title(fact: Fact) -> str:
    """H1 text (spec 06): the error string verbatim in a code span (what an agent pastes into a
    search box: case, digits and ids intact), else the normalized string, else the claim."""
    text = error_string_of(fact) or normalized_of(fact)
    return code_span(text) if text is not None else md_text(fact.claim)


def match_signature(fact: Fact) -> str | None:
    """The normalized string when the H1 shows something else: what `check()` matches on."""
    normalized = normalized_of(fact)
    if normalized is None or error_string_of(fact) is None:
        return None
    return f"Match signature (what `check()` matches): {code_span(normalized)}"


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _signal_part(fact: Fact) -> str | None:
    signal = fact.signal
    if signal is None:
        return None
    words = []
    if signal.status is not None:
        words.append(f"HTTP {signal.status}")
    if signal.error_code:
        words.append(code_span(signal.error_code))
    return " ".join(words) or None


def _target_parts(fact: Fact) -> list[str]:
    target, parts = fact.target, []
    if target.surface is Surface.http:
        parts.append(md_text(f"{target.method} {target.path_template}"))
    if target.sdk is not None:
        sdk = f"SDK {code_span(target.sdk.package)} ({target.sdk.ecosystem})"
        parts.append(sdk + (f" {code_span(target.sdk.versions)}" if target.sdk.versions else ""))
    if target.surface is Surface.cli:
        parts.append("CLI")
    return parts


def target_line(fact: Fact, service: Service) -> str:
    """`Service · METHOD template · SDK … · HTTP status code` (parts the fact has)."""
    parts = [md_text(service.name), *_target_parts(fact), _signal_part(fact)]
    return " · ".join(p for p in parts if p)


def _status_line(fact: Fact) -> str:
    evidence = fact.evidence
    parts = [f"Status: {badge(fact.status)}", f"first seen {utc_date(evidence.first_seen)}"]
    if evidence.last_confirmed:
        parts.append(f"last confirmed {utc_date(evidence.last_confirmed)}")
    vantages = len(evidence.vantages) if evidence.vantages else 0
    if evidence.confirmations is not None:
        tail = f" from {plural(vantages, 'vantage')}" if vantages else ""
        parts.append(plural(evidence.confirmations, "confirmation") + tail)
    elif vantages:
        parts.append(f"seen from {plural(vantages, 'vantage')}")
    if fact.status is Status.reported:
        parts.append("not yet reproduced by a probe")
    if fact.status is Status.stale:
        runs = evidence.stale_counter
        recent = f"the last {runs} probe runs" if runs else "recent probe runs"
        parts.append(f"not reproduced by {recent}; not refuted")
    return " · ".join(parts)


def _sentence(text: str) -> str:
    return text if text.endswith(".") else text + "."


def _fixes(fact: Fact) -> str:
    return "\n".join(
        f"{i}. {_sentence(md_text(render_fix(fix)))}" for i, fix in enumerate(fact.fixes, 1)
    )


def _status_word(status: Status) -> str:
    return "verified" if status in VERIFIED_STATUSES else status.value


def _dimensions(fact: Fact, siblings: Sequence[Fact]) -> str:
    dims = fact.dimensions
    parts = [f"{name}: {md_text(str(getattr(dims, name)))}" for name in DIMENSIONS]
    seen = []
    for sibling in siblings:
        other = sibling.dimensions
        changed = [n for n in DIMENSIONS if getattr(other, n) != getattr(dims, n)]
        label = "/".join(md_text(str(getattr(other, n))) for n in changed)
        when = utc_date(sibling.evidence.last_confirmed or sibling.evidence.first_seen)
        seen.append(f"[{label}]({slug_of(sibling)}.md) ({_status_word(sibling.status)} {when})")
    if seen:
        parts.append("also seen: " + ", ".join(seen))
    return " · ".join(parts)


def _observations(count: int | None) -> str:
    # Invariant 7: aggregates are published only at k ≥ 3 distinct reporter networks.
    if not count:
        return "Observations: none from reporters yet."
    if count < 3:
        return "Observations: fewer than 3 reporter networks."
    return f"Observations: {count} distinct reporter networks."


def _evidence(fact: Fact) -> str:
    evidence, parts = fact.evidence, []
    if evidence.probe:
        _, service, _, slug = evidence.probe.split(":", 3)
        source = f"../../probes/{service}/{slug}.yaml"
        parts.append(f"Probe {code_span(evidence.probe)} (declarative, [source]({source}))")
    if evidence.official_url:
        parts.append(f"official doc: {autolink(evidence.official_url)}")
    first = " · ".join(parts) or "No probe or official document yet."
    return f"{first}\n\n{_observations(evidence.observations)}"


def _check_target(fact: Fact, service: Service) -> dict[str, str]:
    target = fact.target
    if target.surface is Surface.http:
        env_url = getattr(service.dimensions.env, fact.dimensions.env.value)
        http = service.surfaces.http
        base = urlsplit(env_url or (http.base_url if http else f"https://{service.hosts[0]}"))
        return {"method": target.method, "url": f"{base.scheme}://{base.netloc}{target.path_template}"}
    if target.sdk is not None:
        return {"url": f"{target.sdk.ecosystem}:{target.sdk.package}"}
    return {"url": service.hosts[0]}


def check_request(fact: Fact, service: Service) -> dict:
    """The `POST /v0/check` body an agent would send on hitting this fact (spec 03 shape)."""
    body: dict = {"target": _check_target(fact, service)}
    error: dict = {}
    if fact.signal is not None and fact.signal.status is not None:
        error["status"] = fact.signal.status
    if (normalized := normalized_of(fact)) is not None:
        error["body_excerpt"] = normalized
    if error:
        body["error"] = error
    return body


def _machine_access(fact: Fact, service: Service) -> str:
    payload = json.dumps(check_request(fact, service), ensure_ascii=False, separators=(",", ":"))
    quoted = "'" + payload.replace("'", "'\\''") + "'"
    yaml_path = f"facts/{fact.service}/{slug_of(fact)}.yaml"
    signature = match_signature(fact)
    return (
        (f"{signature}\n\n" if signature else "")
        + "```sh\n"
        f"curl -s {CHECK_URL} \\\n"
        "  -H 'content-type: application/json' \\\n"
        f"  -d {quoted}\n"
        "```\n\n"
        f"YAML: [{yaml_path}](../../{yaml_path})"
    )


def fenced(text: str, language: str = "") -> str:
    """A fenced code block that no backtick run inside `text` can close early."""
    longest = max((len(run) for run in re.findall(r"`{3,}", text)), default=2)
    fence = "`" * (longest + 1)
    return f"{fence}{language}\n{text}\n{fence}"


def _example(fact: Fact, service: Service, probe: Probe | None) -> str | None:
    found = example(fact, service, probe)
    if found is None:
        return None
    _, svc, _, slug = found.probe_id.split(":", 3)
    sent = "\n".join(text for _, text, _ in found.steps)
    notes = []
    if any(mark in sent for mark in ("<key>", "<access token>", "<credentials>")):
        notes.append("the real key is elided")
    if INVALID_KEY in sent:
        notes.append(f"{code_span(INVALID_KEY)} is a deliberately wrong key")
    intro = (
        f"What probe [{code_span(found.probe_id)}](../../probes/{svc}/{slug}.yaml) sends "
        f"({md_text(found.env)}) and what it checks in the answer"
        + "".join(f"; {note}" for note in notes)
        + "."
    )
    blocks = [intro]
    many = len(found.steps) > 1
    for number, text, status in found.steps:
        if many:
            tail = f" → HTTP {status}" if status is not None else ""
            blocks.append(f"Step {number}{tail}:")
        blocks.append(fenced(text, "http"))
    blocks.append("Response (only what the probe asserts; other fields omitted):")
    blocks.append(fenced(found.response, "http"))
    return "## Example\n\n" + "\n\n".join(blocks)


def _sdk_table(fact: Fact) -> str | None:
    rows = []
    verified = []
    for r in sdk.raised(fact):
        who = f"{sdk.LANGUAGES[r.ecosystem]} {code_span(r.package)}"
        if not r.official:
            who += " (community)"
        what = f"returns {code_span(r.returns)}" if r.returns else code_span(r.raises or "")
        checks = " · ".join(code_span(sdk.check_expr(r.ecosystem, a, v)) for a, v in r.checks)
        rows.append(f"| {who} | {what} | {checks or '—'} |")
        verified.append(md_text(r.verified))
    if not rows:
        return None
    table = "\n".join(["| SDK | Raises | Check |", "| --- | --- | --- |", *rows])
    return (
        "When an SDK receives this response:\n\n"
        + table
        + "\n\nRead from the SDK source: "
        + "; ".join(verified)
        + "."
    )


def _fix_snippets(fact: Fact) -> str | None:
    blocks = []
    for i, fix in enumerate(fact.fixes, 1):
        snippet = sdk.fix_snippet(fix, fact)
        if snippet is not None:
            language, code = snippet
            blocks.append(f"Fix {i}:\n\n" + fenced(code, language))
    return "\n\n".join(blocks) if blocks else None


def _in_code(fact: Fact) -> str | None:
    parts = [p for p in (_sdk_table(fact), _fix_snippets(fact)) if p]
    return "## In your code\n\n" + "\n\n".join(parts) if parts else None


RELATED_MAX = 6


def _related(facts: Sequence[Fact]) -> str | None:
    if not facts:
        return None
    rows = []
    for f in facts[:RELATED_MAX]:
        parts = [f"- [{title(f)}]({slug_of(f)}.md)", *_target_parts(f)[:1]]
        if (signal := _signal_part(f)) is not None:
            parts.append(signal)
        rows.append(" · ".join(parts))
    return "## Related errors\n\n" + "\n".join(rows)


def _page(*blocks: str) -> str:
    return "\n\n".join([*blocks, "---", FOOTER]) + "\n"


# ── pages ────────────────────────────────────────────────────────────────────────────────────────


def retraction(fact: Fact) -> tuple[str | None, str | None]:
    """(date, reason) of the latest `retracted[:reason]` history entry; the schema has no reason
    field, so `retracted:duplicate_of_x` reads as "duplicate of x"."""
    for entry in reversed(fact.provenance.history or ()):
        change, _, reason = entry.change.partition(":")
        if change == "retracted":
            words = reason.replace("_", " ").replace("-", " ").strip()
            return entry.date, (md_text(words) if words else None)
    return None, None


def retracted_page(fact: Fact) -> str:
    when, reason = retraction(fact)
    line = f"Status: {badge(fact.status)}" + (f" {when}" if when else "")
    line += f" · reason: {reason}" if reason else " · reason not recorded"
    return _page(f"# {title(fact)}", line)


def fact_page(
    fact: Fact,
    service: Service,
    siblings: Sequence[Fact] = (),
    probe: Probe | None = None,
    related: Sequence[Fact] = (),
) -> str:
    """`probe`: the fact's evidence probe, for the Example; `related`: other facts of the
    service with the same error status or endpoint, best first (build.related)."""
    if fact.status is Status.retracted:
        return retracted_page(fact)
    # The claim is quoted under the title, unless it already is the title.
    claim = [f"> {md_text(fact.claim)}"] if error_string_of(fact) or normalized_of(fact) else []
    optional = (_example(fact, service, probe), _in_code(fact), _related(related))
    blocks = [
        f"# {title(fact)}",
        f"**{target_line(fact, service)}**",
        _status_line(fact),
        *claim,
        f"## What to do\n\n{_fixes(fact)}",
        *(b for b in optional[:2] if b),
        f"## Dimensions\n\n{_dimensions(fact, siblings)}",
        f"## Evidence\n\n{_evidence(fact)}",
        *(b for b in optional[2:] if b),
        f"## Machine access\n\n{_machine_access(fact, service)}",
    ]
    return _page(*blocks)


def service_index(service: Service, facts: Sequence[Fact]) -> str:
    hosts = ", ".join(code_span(h) for h in service.hosts)
    header = f"Hosts: {hosts} · {plural(len(facts), 'fact')}" if facts else f"Hosts: {hosts}"
    blocks = [f"# {md_text(service.name)}", header]
    if not facts:
        blocks.append("No facts yet.")
    for kind, heading in KIND_TITLES.items():
        rows = [f for f in facts if f.kind is kind]
        if rows:
            rows.sort(key=lambda f: (f.status is Status.retracted, slug_of(f)))
            items = "\n".join(_index_row(f) for f in rows)
            blocks.append(f"## {heading}\n\n{items}")
    return _page(*blocks)


def _index_row(fact: Fact) -> str:
    row = f"- {badge(fact.status)} · [{title(fact)}]({slug_of(fact)}.md)"
    if fact.status is Status.retracted:
        return row
    return " · ".join([row, *_target_parts(fact)[:1], f"env {fact.dimensions.env.value}"])


def root_index(
    services: Sequence[Service], facts_by_service: Mapping[str, Sequence[Fact]], version: str | None
) -> str:
    total = sum(len(f) for f in facts_by_service.values())
    summary = (
        f"Registry version {version or 'none yet'} · {plural(len(services), 'service')} · "
        f"{plural(total, 'fact')}."
    )
    intro = (
        "Facts about how APIs, SDKs and CLIs behave, for AI agents; each page shows how its fact "
        "was established. " + summary
    )
    blocks = ["# apifacts registry", intro]
    if services:
        header = "| Service | Facts | " + " | ".join(h for h, _ in STATUS_COLUMNS) + " |"
        rule = "| --- | ---: |" + " ---: |" * len(STATUS_COLUMNS)
        rows = []
        for service in services:
            facts = facts_by_service.get(service.key, ())
            counts = [sum(f.status in statuses for f in facts) for _, statuses in STATUS_COLUMNS]
            cells = [f"[{md_text(service.name)}]({service.key}/index.md)", str(len(facts))]
            rows.append("| " + " | ".join(cells + [str(c) for c in counts]) + " |")
        blocks.append("\n".join([header, rule, *rows]))
    else:
        blocks.append("No services registered yet.")
    blocks.append(
        "## Machine access\n\n"
        f"`POST {CHECK_URL}` with the failing request's method, URL and error returns the matching "
        "facts and their typed fixes. Every fact page is titled with its normalized error string."
    )
    return _page(*blocks)


# ── substance of a page (sitemap lastmod) ──────────────────────────────────────────────────────

# What the daily evidence refresh moves on a page without changing what it says: the
# `VOLATILE_EVIDENCE` counters of apifacts/schema/substance.py as `_status_line`, `_dimensions`
# (a sibling's date), `_observations` and `root_index` (the registry version) print them.
_VOLATILE = (
    (re.compile(r" · last confirmed \d{4}-\d{2}-\d{2}"), ""),
    (re.compile(r" · \d+ confirmations?(?: from \d+ vantages?)?"), ""),
    (re.compile(r" · seen from \d+ vantages?"), ""),
    (re.compile(r"by the last \d+ probe runs"), "by recent probe runs"),
    (re.compile(r"\((\w+) \d{4}-\d{2}-\d{2}\)"), r"(\1)"),
    (re.compile(r"Observations: \d+ distinct reporter networks\."), "Observations: ≥ 3."),
    (re.compile(r"Registry version [^ ]+ · "), ""),
)


def substantive(markdown: str) -> str:
    """A generated page without its evidence counters and dates: equal before and after a
    refresh that only re-confirmed its facts (tests/pages: bump every volatile field, compare)."""
    for pattern, replacement in _VOLATILE:
        markdown = pattern.sub(replacement, markdown)
    return markdown


# ── HTML head: the site renders these into <title> and <meta name="description"> ──────────────

HEAD_SUFFIX = " · apifacts"
HEAD_TITLE_MAX = 160  # the whole <title>: engines show ~60 characters but index the rest


def clip_words(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit // 2 else cut).rstrip(" ,;:.") + "…"


def head_title(fact: Fact, service: Service) -> str:
    """`Stripe API 400 amount_too_small: <error string> · apifacts`: service, status and code
    first (what a result list shows), then the page's subject verbatim (`heading`), clipped at a
    word only when the whole title would pass HEAD_TITLE_MAX."""
    signal = fact.signal
    parts = [_one_line(service.name)]
    if signal is not None and signal.status is not None:
        parts.append(str(signal.status))
    if signal is not None and signal.error_code:
        parts.append(_one_line(signal.error_code))
    prefix = " ".join(parts) + ": "
    tail = (" (retracted)" if fact.status is Status.retracted else "") + HEAD_SUFFIX
    return prefix + clip_words(heading(fact), HEAD_TITLE_MAX - len(prefix) - len(tail)) + tail


def head_description(fact: Fact) -> str:
    """The claim: the page's one-line summary (≤ 300 characters by schema)."""
    claim = _one_line(fact.claim)
    return f"Retracted. {claim}" if fact.status is Status.retracted else claim


CC_BY = "https://creativecommons.org/licenses/by/4.0/"


def json_ld(fact: Fact, service: Service) -> dict | None:
    """schema.org `TechArticle` of a fact page, without `url` and `dateModified` (the site adds
    them: the page address and the sitemap lastmod). None for a retracted fact."""
    if fact.status is Status.retracted:
        return None
    about: dict = {"@type": "WebAPI", "name": _one_line(service.name)}
    if service.surfaces.http is not None:
        about["url"] = service.surfaces.http.base_url
    if service.doc_hosts:
        about["documentation"] = f"https://{service.doc_hosts[0]}"
    article = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": heading(fact),
        "description": _one_line(fact.claim),
        "about": about,
        "datePublished": fact.provenance.created,
        "inLanguage": "en",
        "isAccessibleForFree": True,
        "license": CC_BY,
        "publisher": {"@type": "Organization", "name": "apifacts", "url": "https://apifacts.dev"},
    }
    if fact.signal is not None and fact.signal.error_code:
        article["keywords"] = [_one_line(fact.signal.error_code)]
    return article


def service_head(service: Service, facts: Sequence[Fact]) -> tuple[str, str]:
    """(title, description) of a service index; `facts` = its non-retracted facts."""
    name = _one_line(service.name)
    kinds = [h.lower() for k, h in KIND_TITLES.items() if any(f.kind is k for f in facts)]
    what = f" ({', '.join(kinds)})" if kinds else ""
    description = (
        f"What {name} actually returns: {plural(len(facts), 'fact')}{what}, each dated, "
        "with how it was established and what to do. "
        f"Hosts: {', '.join(service.hosts)}."
    )
    return f"{name}: errors, limits and quirks{HEAD_SUFFIX}", description


def error_stub(normalized: str, facts: Sequence[Fact], services: Mapping[str, Service]) -> str:
    rows = "\n".join(
        f"- [{target_line(f, services[f.service])}](../{f.service}/{slug_of(f)}.md)"
        f" · {badge(f.status)} · env {f.dimensions.env.value}"
        for f in facts
    )
    return _page(
        f"# {code_span(normalized)}",
        f"Normalized error string · sha256 {code_span(error_hash(normalized))}",
        rows,
    )
