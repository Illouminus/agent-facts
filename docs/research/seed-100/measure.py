"""Measure deterministic signals for every candidate (2026-10-20). Resumable: re-run skips done rows.
Signals: PyPI downloads/month (pypistats), npm downloads/month, GitHub stars/open issues/pushed_at (gh),
Stack Overflow tag count (SE API, 300 calls/day without key). MCP counts: see mcp-index.py.
No LLM anywhere. Output: data/measurements.json (keyed by service)."""
import json, sys, time, gzip, subprocess, urllib.request, urllib.parse, urllib.error
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import candidates

OUT = Path(__file__).parent / "data" / "measurements.json"
UA = "agent-facts-seed-research/0.1 (+https://github.com/Illouminus/agent-facts; research, <=1 req/s)"

def get_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                return json.loads(raw), r.status
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(5 * (attempt + 1)); continue
            return None, e.code
        except Exception as e:  # network, json
            if attempt < 2:
                time.sleep(2); continue
            return None, f"err:{type(e).__name__}"
    return None, "err"

def pypi(pkg):
    import re
    pkg = re.sub(r"[-_.]+", "-", pkg).lower()   # PEP 503 normalization: pypistats is case/separator-sensitive
    j, st = get_json(f"https://pypistats.org/api/packages/{urllib.parse.quote(pkg)}/recent")
    return (j["data"]["last_month"] if j and "data" in j else None), st

def npm(pkg):
    j, st = get_json(f"https://api.npmjs.org/downloads/point/last-month/{urllib.parse.quote(pkg, safe='@/')}")
    return (j.get("downloads") if j else None), st

def so(tag):
    j, st = get_json(f"https://api.stackexchange.com/2.3/tags/{urllib.parse.quote(tag)}/info?site=stackoverflow")
    if j and j.get("items"):
        return j["items"][0]["count"], st, j.get("quota_remaining")
    return None, st, (j or {}).get("quota_remaining")

def mcp(query):
    j, st = get_json(f"https://registry.modelcontextprotocol.io/v0/servers?search={urllib.parse.quote(query)}&limit=100")
    return (len(j.get("servers", [])) if j else None), st

def gh(repo):
    try:
        out = subprocess.run(["gh", "api", f"repos/{repo}", "--jq",
                              "{stars:.stargazers_count,open_issues:.open_issues_count,pushed_at:.pushed_at,archived:.archived}"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0:
            return json.loads(out.stdout), 200
        return None, (out.stderr.strip()[:80] or "gh-error")
    except Exception as e:
        return None, f"err:{type(e).__name__}"

def measure_one(r):
    m = {"service": r["service"], "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if r["pypi"]:
        m["pypi_month"], m["pypi_status"] = pypi(r["pypi"])
    if r["npm"]:
        m["npm_month"], m["npm_status"] = npm(r["npm"])
    if r["github_repo"]:
        g, st = gh(r["github_repo"]); m["gh"] = g; m["gh_status"] = st
    if r["so_tag"]:
        m["so_count"], m["so_status"], m["so_quota"] = so(r["so_tag"])
    # MCP registry counts come from the local index (mcp-index.py → data/mcp-servers.json): the
    # registry's search endpoint answers in ~24 s per call (measured 2026-10-20), too slow per candidate.
    return m

def main():
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    rows = candidates.rows()
    todo = [r for r in rows if r["service"] not in done]
    print(f"{len(rows)} candidates, {len(done)} measured, {len(todo)} to do", file=sys.stderr, flush=True)
    lock = threading.Lock(); n = 0
    with ThreadPoolExecutor(max_workers=1) as ex:
        futs = {ex.submit(measure_one, r): r for r in todo}
        for f in as_completed(futs):
            r = futs[f]
            try:
                m = f.result()
            except Exception as e:
                m = {"service": r["service"], "error": f"{type(e).__name__}: {e}"[:200]}
            with lock:
                n += 1; done[r["service"]] = m
                OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1))
                print(f"[{n}/{len(todo)}] {r['service']}: pypi={m.get('pypi_month')} npm={m.get('npm_month')} "
                      f"gh={(m.get('gh') or {}).get('stars')} so={m.get('so_count')} mcp={m.get('mcp_official')}", file=sys.stderr, flush=True)
    print("done", file=sys.stderr)

if __name__ == "__main__":
    main()
