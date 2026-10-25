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
from apifacts.pages.errors_index import error_hash, normalized_of
from apifacts.schema.models import VERIFIED_STATUSES, Fact, Kind, Service, Status, Surface

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

CHECK_URL = "https://facts.baillot.dev/v0/check"
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


def title(fact: Fact) -> str:
    """H1 text: the normalized error string in a code span, else the claim (spec 06)."""
    normalized = normalized_of(fact)
    return code_span(normalized) if normalized is not None else md_text(fact.claim)


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
    return (
        "```sh\n"
        f"curl -s {CHECK_URL} \\\n"
        "  -H 'content-type: application/json' \\\n"
        f"  -d {quoted}\n"
        "```\n\n"
        f"YAML: [{yaml_path}](../../{yaml_path})"
    )


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


def fact_page(fact: Fact, service: Service, siblings: Sequence[Fact] = ()) -> str:
    if fact.status is Status.retracted:
        return retracted_page(fact)
    # The claim is quoted under the title, unless it already is the title.
    claim = [f"> {md_text(fact.claim)}"] if normalized_of(fact) is not None else []
    return _page(
        f"# {title(fact)}",
        f"**{target_line(fact, service)}**",
        _status_line(fact),
        *claim,
        f"## What to do\n\n{_fixes(fact)}",
        f"## Dimensions\n\n{_dimensions(fact, siblings)}",
        f"## Evidence\n\n{_evidence(fact)}",
        f"## Machine access\n\n{_machine_access(fact, service)}",
    )


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
