"""The "Known facts" section (spec 07), as plain text, for the plugin and the CLI.

Fix sentences come from the typed `fixes` through `render_fix`, so the closed vocabulary holds even
if an endpoint misbehaves; the server's `fixes_rendered[i]` is shown only for an action this client
does not know yet. Every string from the server is cut to one line without control characters.
"""

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from agentfacts.client.request import Signal

TITLE = "Known facts (agent-facts, CC BY 4.0)"
PAGES = "https://github.com/Illouminus/agent-facts/blob/main/pages"
MAX_FACTS = 5
BADGES = {
    "verified:server:prod": "✅",
    "verified:server:sandbox": "✅",
    "verified:client": "✅",
    "official": "📘",
    "reported": "🟡",
    "stale": "⚪",
}

_FACT_ID = re.compile(r"^af:([a-z0-9][a-z0-9-]{0,63}):([a-z0-9][a-z0-9-]{0,127})$")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_BIDI = re.compile(r"[‎‏‪-‮⁦-⁩]")


def _clean(value: Any, limit: int = 300) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(_CONTROL.sub(" ", _BIDI.sub("", value)).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _fix_lines(fact: Mapping[str, Any]) -> list[str]:
    from agentfacts.fixes.templates import render_fix

    fixes = fact.get("fixes")
    rendered = fact.get("fixes_rendered")
    rendered = rendered if isinstance(rendered, list) else []
    lines = []
    for i, fix in enumerate(fixes if isinstance(fixes, list) else ()):
        try:
            sentence = _clean(render_fix(fix), 200)  # typed parameters may still hold ESC
        except Exception:  # an action newer than this client
            sentence = _clean(rendered[i], 200) if i < len(rendered) else ""
        if sentence:
            lines.append(f"   fix: {sentence}")
    return lines


def _fact_lines(fact: Mapping[str, Any]) -> list[str]:
    status = _clean(fact.get("status"), 32)
    claim = _clean(fact.get("claim"))
    if not claim or status == "retracted":
        return []
    lines = [f"{BADGES.get(status, '•')} {status} · {claim}", *_fix_lines(fact)]
    fact_id = fact.get("id")
    match = _FACT_ID.match(fact_id) if isinstance(fact_id, str) else None
    if match:
        lines.append(f"   {PAGES}/{match[1]}/{match[2]}.md")
    return lines


def _target_line(result: Mapping[str, Any], signal: Signal, facts: list[Mapping]) -> str:
    template = result.get("matched_template")
    template = template if isinstance(template, Mapping) else {}
    method = signal.method or _clean(template.get("method"), 8)
    if "://" in signal.url:
        parts = urlsplit(signal.url)
        path = template.get("path") if isinstance(template.get("path"), str) else parts.path
        where = f"{parts.hostname}{_clean(path, 256)}"
    else:
        where = signal.url
    line = f"{method} {where}" if method else where
    if signal.status is not None:
        line += f" → {signal.status}"
        for fact in facts:
            sig = fact.get("signal")
            if isinstance(sig, Mapping) and sig.get("status") == signal.status:
                code = _clean(sig.get("error_code"), 128)
                if code:
                    line += f" {code}"
                    break
    return line


def render_section(result: Any, signal: Signal, *, show_empty: bool = False) -> str | None:
    """Section body (without the title rule); None when there is nothing to show."""
    if not isinstance(result, Mapping):
        return None
    facts = result.get("facts")
    facts = [f for f in facts if isinstance(f, Mapping)] if isinstance(facts, list) else []
    blocks = [lines for lines in map(_fact_lines, facts) if lines]
    if not blocks and not show_empty:
        return None
    out = [_target_line(result, signal, facts)]
    for lines in blocks[:MAX_FACTS]:
        out.extend(lines)
    if len(blocks) > MAX_FACTS:
        more = f"… {len(blocks) - MAX_FACTS} more facts"
        service = result.get("service")
        if isinstance(service, str) and _SLUG.match(service):
            more += f": {PAGES}/{service}/index.md"
        out.append(more)
    if not blocks:
        unknown = result.get("unknown")
        reason = _clean(unknown.get("reason"), 64) if isinstance(unknown, Mapping) else ""
        out.append(f"no known facts ({reason or 'no_fact_for_signal'})")
    return "\n".join(out)


def title_line(width: int) -> str:
    """The title rule as pytest's `TerminalWriter.sep("─", TITLE)` draws it."""
    fill = "─" * max((width - len(TITLE) - 2) // 2, 1)
    line = f"{fill} {TITLE} {fill}"
    return line + "─" if len(line) < width else line
