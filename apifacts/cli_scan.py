"""`apifacts scan [FILE|-]`: the "Known facts" section for every failed HTTP call in a CI log.

Coding agents fixing red CI read the failing step's log, its annotations and the job summary; this
puts the registry's facts in all three (spec 07, "CI logs"). The calls come from
`apifacts.client.logscan`; each distinct one is asked like the pytest plugin asks: only hosts in the
registry's services list leave the machine (a log is not a call the user chose, unlike
`apifacts check`), tenant subdomains go under their registry host, at most `--max-lookups` checks.

Method (spec 03 refuses a path without one, and a wrong one would be stored as an observation under
the wrong template): a method the log states is used as is, and the error is reported like the
plugin reports it. A log that does not say it: if the registry's templates (the packaged snapshot,
or `APIFACTS_SNAPSHOT`) know exactly one method for that path, the call is asked as a pre-flight,
that method and no `error` object, so nothing is stored (Q5), and the facts are filtered by status
here; otherwise nothing is sent and the output names the `apifacts check` command to run by hand.

Annotations and the step summary show only facts whose signal is the status the log shows; the log
gets the registry's whole answer, service-wide rate-limit facts included, like `apifacts check`.

Advisory: exit 0 whatever is found, the registry down included; 2 only for a usage error.
"""

import json
import shutil
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Annotated, Any, BinaryIO

import typer

from apifacts import __version__

EXIT_OK, EXIT_USAGE = 0, 2
USER_AGENT = f"apifacts-scan/{__version__} (+https://github.com/Illouminus/apifacts)"
MAX_LOOKUPS = 10
SERVICE_WIDE_KINDS = frozenset({"rate_limit", "availability"})

# outcomes
FACTS, NO_FACTS, NOT_REGISTERED = "facts", "no_facts", "not_registered"
METHOD_UNKNOWN, NO_ANSWER, OVER_LIMIT = "method_unknown", "no_answer", "over_limit"


@dataclass
class Call:
    found: Any  # logscan.Found
    outcome: str = NOT_REGISTERED
    method_source: str | None = None  # "log", or "registry" (the only registered method)
    answer: dict[str, Any] | None = None
    section: str | None = None  # the registry's answer, as `apifacts check` prints it
    relevant: str | None = None  # the facts about this status only (annotation, summary)
    notes: list[str] = field(default_factory=list)


def read_tail(fh: BinaryIO, limit: int) -> str:
    """The last `limit` bytes of a stream (the failure is at the end of a log)."""
    try:
        size = fh.seek(0, 2)
        fh.seek(max(0, size - limit))
        data = fh.read(limit)
    except (OSError, ValueError):  # a pipe: keep a rolling tail
        data = b""
        while chunk := fh.read(1 << 16):
            data = (data + chunk)[-limit:]
    return data.decode("utf-8", "replace")


def _status_filtered(answer: dict[str, Any], status: int | None) -> dict[str, Any]:
    """A pre-flight answer lists the template's facts: keep the ones for this status, plus the
    service-wide kinds the server's cascade would also return (spec 03, step 3)."""
    facts = answer.get("facts")
    facts = facts if isinstance(facts, list) else []
    kept = [
        f
        for f in facts
        if isinstance(f, Mapping)
        and (
            f.get("kind") in SERVICE_WIDE_KINDS
            or (isinstance(f.get("signal"), Mapping) and f["signal"].get("status") == status)
        )
    ]
    out = {**answer, "facts": kept}
    if not kept:
        out["unknown"] = {"reason": "no_fact_for_signal", "stored_as_observation": False}
    return out


def _check_hint(call: Call) -> str:
    signal = call.found.signal
    return (
        f"method not in the log; to look it up: apifacts check {signal.url} -X <METHOD>"
        f" --status {signal.status}"
    )


def _where(signal: Any) -> str:
    line = signal.url.split("://", 1)[1]
    if signal.method:
        line = f"{signal.method} {line}"
    return f"{line} → {signal.status}" if signal.status is not None else line


def lookup(found: list[Any], client: Any, snapshot: Any, max_lookups: int) -> list[Call]:
    from apifacts.client.render import render_section

    calls, sent = [], 0
    for item in found:
        call = Call(item)
        calls.append(call)
        signal = item.signal
        host = client.registered_host(signal.host)
        if host is None:
            continue  # NOT_REGISTERED: nothing leaves the machine
        if host != signal.host:
            signal = signal.with_host(host)
        payload: dict[str, Any] | None
        if signal.method is not None:
            call.method_source = "log"
            payload = signal.payload()
        else:
            methods = snapshot().methods_for(signal.url) if snapshot else frozenset()
            if len(methods) != 1:
                call.outcome = METHOD_UNKNOWN
                call.notes.append(_check_hint(call))
                continue
            (method,) = methods
            signal = replace(signal, method=method)
            call.method_source = "registry"
            payload = {"target": signal.payload()["target"]}  # pre-flight: never stored
            call.notes.append(
                f"method not in the log: {method} is the only one registered for this path;"
                " looked up without reporting the error"
            )
        if sent >= max_lookups:
            call.outcome = OVER_LIMIT
            call.notes = [f"not looked up: --max-lookups {max_lookups} reached"]
            continue
        sent += 1
        answer = client.check(payload)
        if answer is None:
            call.outcome = NO_ANSWER
            call.notes = [f"registry did not answer: {client.last_error}"]
            continue
        if call.method_source == "registry":
            answer = _status_filtered(answer, signal.status)
        call.answer = answer
        call.section = _without_code(render_section(answer, signal, show_empty=True), call)
        matching = _for_status(answer, signal.status)
        if matching:  # annotations and the summary: only facts about this status
            call.outcome = FACTS
            call.relevant = _without_code(
                render_section({**answer, "facts": matching}, signal), call
            )
        else:
            call.outcome = NO_FACTS
    return calls


def _for_status(answer: Mapping[str, Any], status: int | None) -> list[Any]:
    """Facts whose signal is this status. The server's cascade (spec 03, step 3) also returns
    the service's rate-limit facts for any error: right in the log, noise in an annotation."""
    facts = answer.get("facts")
    return [
        f
        for f in (facts if isinstance(facts, list) else [])
        if isinstance(f, Mapping)
        and isinstance(f.get("signal"), Mapping)
        and f["signal"].get("status") == status
    ]


def _without_code(section: str | None, call: Call) -> str | None:
    """A looked-up-without-error call: the target line names no error code (the log gave no
    body the server read; the first fact's code would be a guess)."""
    if section is None or call.method_source != "registry":
        return section
    head, sep, rest = section.partition("\n")
    status = call.found.signal.status
    return head.split(" → ", 1)[0] + (f" → {status}" if status is not None else "") + sep + rest


def _block(call: Call, *, relevant: bool = False) -> str | None:
    """The plain text for one call, or None for calls that were not asked. `relevant`: the
    summary's version, facts about this status only and nothing for a call without any."""
    section = call.relevant if relevant else call.section
    if section is not None:
        return "\n".join([section, *(f"   ({note})" for note in call.notes)])
    if call.outcome == METHOD_UNKNOWN or (call.outcome in (NO_ANSWER, OVER_LIMIT) and not relevant):
        return "\n".join([_where(call.found.signal), *(f"   ({n})" for n in call.notes)])
    return None


def summary_line(calls: list[Call]) -> str:
    count = {k: sum(c.outcome == k for c in calls) for k in (FACTS, NO_FACTS, NOT_REGISTERED)}
    asked = count[FACTS] + count[NO_FACTS]
    parts = [f"{len(calls)} failed HTTP call{'s' if len(calls) != 1 else ''} in the log"]
    if calls:
        parts.append(f"{asked} looked up, {count[FACTS]} with known facts")
    if count[NOT_REGISTERED]:
        parts.append(f"{count[NOT_REGISTERED]} to hosts the registry does not know (not sent)")
    unknown = sum(c.outcome == METHOD_UNKNOWN for c in calls)
    if unknown:
        parts.append(f"{unknown} without a method (not sent)")
    return "apifacts scan: " + "; ".join(parts)


def github_output(calls: list[Call], *, annotations: bool) -> list[str]:
    """Annotation lines (calls with facts) and the step-summary section (any call worth showing)."""
    from apifacts.client.github_actions import append_summary, fenced, warning
    from apifacts.client.render import TITLE

    lines = []
    if annotations:
        for call in calls:
            if call.outcome == FACTS and call.relevant:
                head, _, rest = call.relevant.partition("\n")
                body = "\n".join([rest, *(f"({note})" for note in call.notes)]).strip()
                lines.append(warning(body, title=f"apifacts: {head}"))
    blocks = [b for c in calls if (b := _block(c, relevant=True))]
    if blocks:
        append_summary(
            f"### {TITLE}\n\n{summary_line(calls)}. Facts are verified by probes; "
            "fact pages at https://apifacts.dev.\n\n" + fenced("\n\n".join(blocks)) + "\n"
        )
    return lines


def _as_json(calls: list[Call]) -> dict[str, Any]:
    return {
        "summary": summary_line(calls),
        "calls": [
            {
                "line": c.found.line,
                "source": c.found.source,
                "method": c.found.signal.method,
                "url": c.found.signal.url,  # scrubbed: scheme, host, path
                "status": c.found.signal.status,
                "outcome": c.outcome,
                "method_source": c.method_source,
                "notes": c.notes,
                "answer": c.answer,
            }
            for c in calls
        ],
    }


def scan(
    log: Annotated[
        Path,
        typer.Argument(metavar="[FILE|-]", help="Log file to scan; '-' or nothing = stdin."),
    ] = Path("-"),
    offline: Annotated[
        bool, typer.Option(help="Answer from the packaged snapshot or APIFACTS_SNAPSHOT.")
    ] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Print the calls and answers.")] = False,
    github: Annotated[
        bool | None,
        typer.Option(
            "--github/--no-github",
            help="Annotations + $GITHUB_STEP_SUMMARY (default: on when GITHUB_ACTIONS=true).",
        ),
    ] = None,
    max_lookups: Annotated[
        int, typer.Option(min=0, max=50, help="Checks sent at most (distinct calls).")
    ] = MAX_LOOKUPS,
) -> None:
    """Find failed HTTP calls in a CI log and print what the registry knows about each."""
    from apifacts.client.github_actions import is_github_actions, safe_log_line
    from apifacts.client.logscan import MAX_LOG_BYTES
    from apifacts.client.logscan import scan as scan_text
    from apifacts.client.render import title_line
    from apifacts.client.settings import Settings
    from apifacts.client.transport import Client

    try:
        if str(log) == "-":
            text = read_tail(sys.stdin.buffer, MAX_LOG_BYTES)
        else:
            with log.open("rb") as fh:
                text = read_tail(fh, MAX_LOG_BYTES)
    except OSError as exc:
        typer.echo(f"error: cannot read {log}: {exc}", err=True)
        raise typer.Exit(EXIT_USAGE) from None
    github = is_github_actions() if github is None else github

    found = scan_text(text)
    settings = Settings.from_env()
    if found and settings.disabled and not offline:
        typer.echo("apifacts scan: APIFACTS_DISABLE is set; nothing sent", err=True)
        found = []
    client = Client(settings.endpoint, USER_AGENT, offline=offline, snapshot=settings.snapshot)
    loaded: list[Any] = []

    def snapshot() -> Any:
        if not loaded:
            from apifacts.client.offline import Snapshot

            try:
                loaded.append(Snapshot.load(settings.snapshot))
            except Exception:  # an unreadable snapshot only means: no inference
                loaded.append(None)
        return loaded[0] or _EMPTY

    calls = lookup(found, client, snapshot, max_lookups) if found else []
    if client.last_error:  # a registry that is down makes every host look unknown: say so
        typer.echo(f"apifacts scan: {client.last_error}", err=True)

    out: list[str] = []
    if json_out:
        out.append(json.dumps(_as_json(calls), indent=2, sort_keys=True))
    else:
        width = min(shutil.get_terminal_size((80, 24)).columns, 100)
        for call in calls:
            if (block := _block(call)) is not None:
                out.extend([title_line(width), *block.splitlines(), ""])
        out.append(summary_line(calls))
        if github:
            out = [safe_log_line(line) for line in out]
    if github:
        out.extend(github_output(calls, annotations=not json_out))
    typer.echo("\n".join(out))


class _NoTemplates:
    def methods_for(self, url: str) -> frozenset[str]:
        return frozenset()


_EMPTY = _NoTemplates()
