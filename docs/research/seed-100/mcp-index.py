"""Fetch the whole official MCP registry once (paginated) → data/mcp-servers.json
[{name, description}]. Counting per candidate happens in rank.py by word-boundary match."""
import json, time, urllib.request, urllib.parse
from pathlib import Path
OUT = Path(__file__).parent / "data" / "mcp-servers.json"
UA = "agent-facts-seed-research/0.1 (+https://github.com/Illouminus/agent-facts)"
base = "https://registry.modelcontextprotocol.io/v0/servers?limit=100&version=latest"  # the plain list repeats every version of every server (measured: 51 unique names per 100 rows)
cursor, items, pages = None, [], 0
while True:
    url = base + (f"&cursor={urllib.parse.quote(cursor)}" if cursor else "")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        j = json.loads(r.read())
    pages += 1
    for s in j.get("servers", []):
        srv = s.get("server", s)
        items.append({"name": srv.get("name", ""), "description": srv.get("description", "") or ""})
    meta = j.get("metadata") or {}
    cursor = meta.get("nextCursor") or meta.get("next_cursor")
    print(f"page {pages}: total {len(items)} cursor={bool(cursor)}", flush=True)
    if pages % 50 == 0 or not cursor:
        OUT.write_text(json.dumps({"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pages": pages,
                                   "complete": not cursor, "servers": items}, ensure_ascii=False))
    if not cursor:
        break
    time.sleep(0.2)
print("saved", len(items), "servers (unique names:", len({i["name"] for i in items}), ")")
