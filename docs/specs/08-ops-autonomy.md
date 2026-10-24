# 08 · Operations and autonomy

**Done when:** the four timers below run on illouminus as user units, `state/projects/agent-facts.md`
receives the weekly journal line automatically, the Monday digest arrives in Telegram with a single
"✅ Publish batch" tap for outward publications, and the kill switch stops runner + bot within one tick
(tested on the host with a dry run).

## Timers (systemd user units, `ops/systemd/`)

| Unit | Schedule | Does |
|------|----------|------|
| `agentfacts-probe.timer` | every 15 min | `agentfacts probe run --due --max 50` |
| `agentfacts-quorum.timer` | hourly | `agentfacts quorum run && agentfacts bot publish` |
| `agentfacts-refresh.timer` | daily 03:00 Europe/Paris | `agentfacts probe run --refresh-evidence` (counters → facts/, added 24.10.2026) |
| `agentfacts-pages.timer` | on merge (CI) | pages build in CI, not on the host |
| `agentfacts-digest.timer` | Mon 08:00 Europe/Paris | `ops/digest.py` → Telegram (question class, D-062) |

Deploy: `vps-auto-deploy` pattern (GHCR image, forced-command SSH restart, health check on `/healthz`).

GitHub access on the host: the bot uses only its own token `agent-facts-bot` (repo-scoped PAT, D-089);
`deploy.sh` fetches the public repo anonymously. Units carry the seccomp/prctl hardening that works for
user units; mount-namespace confinement (read-only system, per-unit key access) is impossible in user
units on illouminus and needs system units under a dedicated user (`ops/README.md` → Hardening).
API behind Caddy at `facts.baillot.dev` `[tap: DNS record once]`.

## Weekly digest (one message, one tap)

```
agent-facts · week 44
facts: 112 (+9) · verified 71 · reported 31 · stale 4 · retracted 0
check(): 143 calls from 27 networks · 11 unregistered targets (top: api.notion.com; hosts known only for seed candidates, the rest is "other")
probes: 1 840 runs · 0 budget violations · keys missing: [hubspot-test]
needs a probe (agent-hours): 6 reported facts  → card created
publications proposed (batch #7, 4 items):
  1. stripe/stripe-python#1234 — issue: idempotency error string changed in 12.2.0 (verified prod)
  2. SO 79xxxxxx — answer: Slack "invalid_blocks" when text > 3000 (verified prod)
  3. …
[✅ Publish batch #7]  [⏭ Skip this week]
```

Rules for the batch (decision 2026-10-20): templates and the vendor list are pre-approved in
`ops/publish-policy.yaml`; every item links a `verified:*` fact; no vendor opinions, no vulnerabilities;
the tap publishes all items, a skip keeps them for the next batch; nothing is ever published without
the tap.

## Autonomy split (decision 2026-10-20)

| Agent decides alone | Needs Edouard's tap | Message only (no question) |
|---------------------|---------------------|----------------------------|
| new facts and statuses, probe schedules, pages, plugin releases, keyless services, kill switch, "needs a probe" cards | money (any paid resource, budget overrun), new accounts/keys on third-party services, changes to ingestion rules (`03`, `05` thresholds), the weekly publication batch | account ban / ToS change, key rotation needed, vendor complaint, kill switch triggered |

## Budgets

| Budget | Value |
|--------|-------|
| Edouard | 2–3 h once (seed list, accounts via `keyput`, repo public, DNS); then ~10–15 min/week |
| Agent | W0–W8 ≈ 2–3 sessions; run ≈ 1 agent-hour/week (unmeasured estimate) |
| Money | $0 target for wave 1: free tiers and sandboxes; CI minutes on the private repo until public |

## Megabrain state

`projects/agent-facts.md` journal (newest first) gets a line per merged W-package and per weekly digest;
cards in `state/tasks/` for "needs a probe" (machine: vps) and for the taps (waiting_edouard). Commits
only via `bin/state-commit --as agent-facts <paths>`.
