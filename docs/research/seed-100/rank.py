"""Rank candidates from data/measurements.json → data/ranked.csv + data/ranked.json and pick wave 1.
Score (0..1): 0.45 usage(log downloads/month, max of pypi/npm) + 0.15 stars + 0.25 pain(SO tag count)
+ 0.15 agent pull (official MCP registry servers whose name/description mention the service, local index); each component min-max of log1p
across the universe. Feasibility multiplier: tos prohibited → excluded; restricted ×0.8;
probe_class keyless/sandbox ×1.0, key_free ×0.95, local ×0.85, trial ×0.8, paid ×0.7.
Wave 1 = top by score among probe_class ∈ {keyless, sandbox, key_free}, ≤ 2 per category, ≥ 3 keyless,
no hyperscalers or umbrellas (aws/gcp/azure/google-workspace; github-actions = github), one service per shared SDK package."""
import json, csv, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import candidates
D = Path(__file__).parent / "data"
M = json.loads((D / "measurements.json").read_text())
W = {"usage": 0.45, "stars": 0.15, "pain": 0.25, "mcp": 0.15}
FEAS = {"keyless": 1.0, "sandbox": 1.0, "key_free": 0.95, "local": 0.85, "trial": 0.8, "paid": 0.7}
TOS = {"ok": 1.0, "restricted": 0.8, "prohibited": 0.0}

import re
IDX = json.loads((D / "mcp-servers.json").read_text())["servers"] if (D / "mcp-servers.json").exists() else []
VENDOR_PREFIX = {"google", "meta", "aws", "microsoft", "amazon", "open", "azure", "apple", "us", "uk", "eu", "api", "data", "x"}
GENERIC = {"workspace", "data", "graph", "api", "engine", "cloud", "hub", "actions", "search", "library", "registry", "central", "date", "reader", "console", "marketing", "ads", "gov", "fr", "central", "edgar", "meteo", "food facts", "open data"}
def mcp_count(service):
    parts = service.split("-")
    variants = {service, service.replace("-", " "), service.replace("-", "")}
    if len(parts) > 1 and parts[0] in VENDOR_PREFIX:
        variants.add("-".join(parts[1:])); variants.add(" ".join(parts[1:])); variants.add("".join(parts[1:]))
    variants -= GENERIC
    pats = [re.compile(r"\b" + re.escape(v) + r"\b", re.I) for v in variants if len(v) >= 3]
    # registry names are namespaced (io.github.<owner>/<name>): match the part after "/" only, so that the
    # namespace does not count every GitHub-hosted server as a "github" server (measured: 28 612 → real count)
    return sum(1 for srv in IDX if any(p.search(srv["name"].split("/")[-1]) or p.search(srv["description"]) for p in pats))

rows = []
for r in candidates.rows():
    m = M.get(r["service"], {})
    dl = max([x for x in (m.get("pypi_month"), m.get("npm_month")) if isinstance(x, int)], default=0)
    stars = (m.get("gh") or {}).get("stars") or 0
    so = m.get("so_count") or 0
    mcp = mcp_count(r["service"]) if IDX else 0
    rows.append({**r, "downloads_month": dl, "stars": stars, "so_count": so, "mcp_servers": mcp,
                 "pypi_status": m.get("pypi_status"), "npm_status": m.get("npm_status"),
                 "gh_status": m.get("gh_status"), "so_status": m.get("so_status"), "measured": bool(m)})

def norm(key):
    vals = [math.log1p(x[key]) for x in rows]
    lo, hi = min(vals), max(vals)
    for x, v in zip(rows, vals):
        x["n_" + key] = (v - lo) / (hi - lo) if hi > lo else 0.0

for k in ("downloads_month", "stars", "so_count", "mcp_servers"):
    norm(k)
for x in rows:
    raw = (W["usage"] * x["n_downloads_month"] + W["stars"] * x["n_stars"] + W["pain"] * x["n_so_count"]
           + W["mcp"] * x["n_mcp_servers"])
    x["score_raw"] = round(raw, 4)
    x["score"] = round(raw * FEAS[x["probe_class"]] * TOS[x["tos"]], 4)
rows.sort(key=lambda x: -x["score"])
for i, x in enumerate(rows, 1):
    x["rank"] = i

cols = ["rank", "service", "vendor", "category", "probe_class", "tos", "score", "score_raw", "downloads_month",
        "stars", "so_count", "mcp_servers", "pypi", "npm", "github_repo", "so_tag", "pypi_status", "npm_status",
        "gh_status", "so_status"]
with (D / "ranked.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
(D / "ranked.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))

# wave 1 pick
# Hyperscalers are excluded from wave 1: their surface is hundreds of services, a dense first wave needs
# one narrow interface per service (S3, Lambda, GCS … come as sub-services in later waves).
PLATFORM = {"aws", "gcp", "azure", "google-workspace", "github-actions"}  # umbrellas / same interface as github
wave, per_cat, keyless, seen_pkgs = [], {}, 0, set()
for x in rows:
    if x["probe_class"] not in ("keyless", "sandbox", "key_free") or x["tos"] != "ok":
        continue
    if x["service"] in PLATFORM or per_cat.get(x["category"], 0) >= 2:
        continue
    pkgs = {p for p in (x["pypi"], x["npm"]) if p}
    if pkgs & seen_pkgs:          # same SDK as an already picked service (google-* family): one per SDK
        continue
    seen_pkgs |= pkgs
    wave.append(x); per_cat[x["category"]] = per_cat.get(x["category"], 0) + 1
    keyless += x["probe_class"] == "keyless"
    if len(wave) == 10:
        break
if keyless < 3:  # swap tail entries for the best keyless ones not yet in
    extra = [x for x in rows if x["probe_class"] == "keyless" and x["tos"] == "ok" and x not in wave]
    while keyless < 3 and extra:
        wave.pop(); wave.append(extra.pop(0)); keyless += 1
(D / "wave1.json").write_text(json.dumps([x["service"] for x in wave], indent=1))

unmeasured = [x["service"] for x in rows if not x["measured"]]
bad = [(x["service"], k, x[k]) for x in rows for k in ("pypi_status", "npm_status", "gh_status", "so_status")
       if x[k] not in (None, 200) and x.get(k.split("_")[0]) is not None]
print(f"ranked {len(rows)}; unmeasured {len(unmeasured)}; lookups not 200: {len(bad)}")
print("wave 1:", [x["service"] for x in wave])
print("\ntop 30:")
for x in rows[:30]:
    print(f"{x['rank']:>3} {x['service']:<22} {x['category']:<16} {x['probe_class']:<9} score={x['score']:.3f} "
          f"dl={x['downloads_month']:>11,} stars={x['stars']:>6,} so={x['so_count']:>6,} mcp={x['mcp_servers']}")
if bad:
    print("\nlookups to fix (service, field, status):")
    for b in bad: print("  ", b)
