#!/usr/bin/env python3
"""Tell IndexNow (Bing, Yandex, Seznam, Naver…; https://www.indexnow.org/documentation) which pages
of apifacts.dev changed, once a day after the evidence refresh has been deployed.

    ops/indexnow.py [--sitemap URL] [--state var/indexnow.json] [--endpoint URL] [--dry-run]

An agent debugging a failed call searches the exact error string; Bing answers ChatGPT search and
many agent search APIs, and IndexNow is how a page gets re-crawled there without waiting.

What is "changed" comes from the served sitemap (the local API by default, the same bytes Caddy
serves): a URL whose `<lastmod>` differs from the one last submitted, or that is new, plus a URL
that left the sitemap (IndexNow wants deletions too). `lastmod` moves only when a page's substance
changes (apifacts/api/site.py), so a night whose only news is "re-confirmed" submits nothing.
The first run submits every page. One POST carries them all (the protocol allows 10,000 per
request; above that, several POSTs). Only a 200/202 answer advances `var/indexnow.json`: a failed
run is retried in full the next day. The key is public by design (`INDEXNOW_KEY`, served at
`https://apifacts.dev/<key>.txt`).

Exit codes: 0 submitted or nothing to submit (also a dry run), 1 the sitemap or a submission
failed, 2 usage.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from apifacts.api.site import INDEXNOW_KEY, SITE

LOCAL_SITEMAP = "http://127.0.0.1:8795/sitemap.xml"
ENDPOINT = "https://api.indexnow.org/indexnow"
HOST = urlsplit(SITE).hostname
KEY_LOCATION = f"{SITE}/{INDEXNOW_KEY}.txt"
BATCH = 10_000  # protocol maximum per POST
ACCEPTED = (200, 202)  # 202: received, key validation pending
_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

Post = Callable[[str, dict], httpx.Response]


def parse_sitemap(xml: bytes) -> dict[str, str]:
    """`{loc: lastmod}` of a sitemaps.org urlset; a URL without lastmod maps to ""."""
    root = ET.fromstring(xml)
    return {
        (url.findtext(f"{_NS}loc") or "").strip(): (url.findtext(f"{_NS}lastmod") or "").strip()
        for url in root.iter(f"{_NS}url")
        if (url.findtext(f"{_NS}loc") or "").strip()
    }


def to_submit(current: Mapping[str, str], submitted: Mapping[str, str]) -> list[str]:
    """New or re-dated URLs, then URLs that left the sitemap; only our host's (IndexNow refuses
    the whole batch over one foreign URL)."""
    changed = [u for u in sorted(current) if submitted.get(u) != current[u]]
    gone = [u for u in sorted(submitted) if u not in current]
    return [u for u in changed + gone if urlsplit(u).hostname == HOST]


def read_state(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        message = f"{path}: unreadable state ({exc}); move it away to resubmit everything"
        raise ValueError(message) from None
    return data if isinstance(data, dict) else {}


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def payload(urls: Sequence[str]) -> dict:
    return {"host": HOST, "key": INDEXNOW_KEY, "keyLocation": KEY_LOCATION, "urlList": list(urls)}


def _post(endpoint: str, body: dict) -> httpx.Response:
    return httpx.post(endpoint, json=body, timeout=30)


def submit(urls: Sequence[str], endpoint: str, post: Post = _post) -> tuple[bool, list[dict]]:
    """POST in batches of BATCH; stops at the first refused batch. (all accepted, per-batch log)."""
    log: list[dict] = []
    for start in range(0, len(urls), BATCH):
        batch = urls[start : start + BATCH]
        try:
            r = post(endpoint, payload(batch))
            entry = {"urls": len(batch), "status": r.status_code}
            if r.status_code not in ACCEPTED:
                entry["body"] = r.text[:200]
        except httpx.HTTPError as exc:
            entry = {"urls": len(batch), "status": None, "error": str(exc)[:200]}
        log.append(entry)
        if entry["status"] not in ACCEPTED:
            return False, log
    return True, log


def _args(argv: Sequence[str] | None) -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--sitemap", default=LOCAL_SITEMAP, help="sitemap URL to read")
    p.add_argument("--state", type=Path, default=root / "var" / "indexnow.json")
    p.add_argument("--endpoint", default=ENDPOINT)
    p.add_argument("--dry-run", action="store_true", help="print what would be submitted")
    return p.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    post: Post = _post,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    try:
        args = _args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        state = read_state(args.state)
        r = httpx.get(args.sitemap, timeout=30)
        r.raise_for_status()
        current = parse_sitemap(r.content)
    except (ValueError, httpx.HTTPError, ET.ParseError) as exc:
        print(f"indexnow: {exc}", file=sys.stderr)
        return 1
    submitted = state.get("submitted") if isinstance(state.get("submitted"), dict) else {}
    urls = to_submit(current, submitted)
    if args.dry_run:
        print(f"indexnow: would submit {len(urls)} of {len(current)} URLs to {args.endpoint}")
        for url in urls:
            print(url)
        return 0
    at = now().isoformat(timespec="seconds").replace("+00:00", "Z")
    if not urls:
        print(f"indexnow: nothing changed ({len(current)} URLs)")
        last_run = {"at": at, "urls": 0}
        write_state(args.state, {**state, "submitted": submitted, "last_run": last_run})
        return 0
    ok, log = submit(urls, args.endpoint, post)
    run = {"at": at, "urls": len(urls), "batches": log, "ok": ok}
    write_state(
        args.state, {**state, "submitted": dict(current) if ok else submitted, "last_run": run}
    )
    statuses = ", ".join(str(b["status"]) for b in log)
    print(f"indexnow: {'submitted' if ok else 'FAILED'} {len(urls)} URLs (HTTP {statuses})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
