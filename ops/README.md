# ops — agent-facts on illouminus (W8)

Spec: `docs/specs/08-ops-autonomy.md`. No Docker: a git checkout of this repo at
`~/apps/agent-facts`, detached at the deployed sha, with its own `.venv` (`uv sync --frozen
--no-dev`). Nothing in ops calls an LLM.

| Path on the host | What |
|------------------|------|
| `~/apps/agent-facts/` | checkout (detached HEAD = deployed sha) |
| `var/results.jsonl`, `var/probe-state.sqlite` | probe runs and budgets (spec 04) |
| `var/evidence-pending.sqlite`, `var/evidence-refresh.json` | counters waiting for the daily refresh, its marker |
| `var/bot-state.json` | day and refresh of the last "daily evidence refresh" PR |
| `var/observations.sqlite` | check() observations and counters (spec 03) |
| `var/deploy/` | `deployed` (sha), `deploy.log`, parked `facts-unapplied-*.patch` |
| `var/publications.jsonl` | published items (once the publish policy is approved) |
| `ops/KILL` | kill switch file (gitignored) |
| `~/.config/systemd/user/agentfacts-*` | symlinks to `ops/systemd/` (`systemctl --user link`) |

| Unit | When | Enabled |
|------|------|---------|
| `agentfacts-api.service` | always, `127.0.0.1:8795`, 1 worker, no access log | yes |
| `agentfacts-probe.timer` | every 15 min, `probe run --due --max 50 --vantage illouminus` | yes |
| `agentfacts-digest.timer` | Monday 08:00 Europe/Paris, `ops/digest.py` | yes |
| `agentfacts-refresh.timer` | daily 03:00 Europe/Paris, `probe run --refresh-evidence` | by hand after the deploy that adds it |
| `agentfacts-quorum.timer` | hourly, quorum + bot (own token, verified-only auto-merge) | after the D-089 PR |

## First install (once)

```bash
gh repo clone Illouminus/agent-facts ~/apps/agent-facts      # gh keyring: the repo is private
cd ~/apps/agent-facts && git checkout --detach origin/main
~/.local/bin/uv sync --frozen --no-dev && mkdir -p var
export XDG_RUNTIME_DIR=/run/user/$(id -u)                     # over non-interactive ssh
for u in ops/systemd/agentfacts-*; do systemctl --user link "$PWD/$u"; done
systemctl --user enable --now agentfacts-api.service
curl -s 127.0.0.1:8795/healthz
.venv/bin/agentfacts probe run --all --vantage illouminus --root .   # first run, before the timer
systemctl --user enable --now agentfacts-probe.timer          # one call per unit
systemctl --user enable --now agentfacts-digest.timer
```

Units are links into the checkout: when `ops/systemd/` changes, `ops/deploy.sh` links unit files
that are not linked yet and runs `daemon-reload`; enabling a new unit stays a deliberate step
(`systemctl --user enable --now agentfacts-refresh.timer`).

## Deploy

On merge, `.github/workflows/deploy.yml` (after CI succeeds on `main`) ssh-es the sha to a forced
command; nothing else can run with that key:

```
command="/home/ubuntu/apps/agent-facts/ops/deploy.sh",restrict ssh-ed25519 AAAA… gha-deploy-agent-facts
```

Test the restriction over the public OpenSSH port (Tailscale SSH on `ssh illouminus` ignores
`authorized_keys`): `ssh -F /dev/null -i <key> -p 64224 ubuntu@<public ip> <sha>`.

Over ssh only a sha ahead of the deployed one is accepted (no downgrade with a leaked key). By
hand: `~/apps/agent-facts/ops/deploy.sh <40-hex sha on origin/main>`, any sha on main, so this is
also the rollback. Exit 1 = rolled back (prod alive on the old sha), 3 = rollback failed too.

The API loads `facts/` and `services/` only at startup. A bare `git pull` / `git checkout` in
`~/apps/agent-facts` leaves it answering from the old registry until `systemctl --user restart
agentfacts-api` — `deploy.sh` always restarts, so prefer it. `/healthz` → `registry_version` shows
which registry is served; `probes_last_run` is read from `var/results.jsonl` on each call (no
restart needed after a probe tick).

The probe runner writes `facts/` in place on a status change, a new vantage and the daily refresh;
until the bot publishes those edits, `deploy.sh` carries them across checkouts as a patch, and
parks a patch that no longer applies in `var/deploy/` instead of dropping it. The journal hook
(`ops/state_journal.py --prev`) writes a megabrain line only when a deploy changes what the
registry says (new, removed or re-statused facts, claims), never for counters or code.

## Bot token

The bot (`agentfacts bot publish`) talks to GitHub only with its own fine-grained PAT, Contents +
Pull requests on this repository: `keyput agent-facts-bot` → `~/.private_keys/agent-facts-bot.key`
(D-089). `gh` gets it as `GH_TOKEN`; git push/fetch/ls-remote get it through an env-only credential
helper that first resets `~/.gitconfig`'s `gh auth git-credential` (the owner's login, every
repository). Missing file → `error: no bot token …`, exit 1, nothing pushed. `deploy.sh` fetches
the public repo with `-c credential.helper=` (anonymous).

## Hardening

Every `agentfacts-*.service` sets `NoNewPrivileges`, `RestrictSUIDSGID`, `LockPersonality`,
`RestrictRealtime`, `RestrictNamespaces`, `SystemCallArchitectures=native`,
`SystemCallFilter=@system-service` (`EPERM`), `MemoryDenyWriteExecute`, `RestrictAddressFamilies`
(unix, inet, inet6, netlink) and `UMask=0077` — checked on the host 2026-10-24 (`NoNewPrivs: 1`,
`Seccomp: 2`; probe, quorum, bot dry runs, uvicorn, gh, git and HTTPS work under it).

Impossible in user units on illouminus (Ubuntu 24.04, systemd 255,
`kernel.apparmor_restrict_unprivileged_userns=1`): the user manager's user namespace lands in the
`unprivileged_userns` AppArmor profile without `CAP_SYS_ADMIN`, so there is no mount namespace.
`ProtectSystem`, `ProtectHome`, `PrivateTmp`, `ReadWritePaths`, `InaccessiblePaths`, `ProtectProc`,
`ProtectKernelTunables`, `ProtectControlGroups` are silently ignored; `PrivateUsers`,
`PrivateDevices`, `TemporaryFileSystem`, `BindReadOnlyPaths`, `ProtectClock` make the unit fail with
`226/NAMESPACE` ("Failed to set up mount namespacing: Operation not supported"). Hence no read-only
filesystem and no per-unit key access: every unit runs as `ubuntu` and could read all of
`~/.private_keys`. Way out (root, Edouard's call): system units with `User=agentfacts`, a dedicated
user whose own keys directory holds only the agent-facts keys (mount namespaces work for system
units); lifting the AppArmor restriction would weaken the whole host and is not proposed.

Check a property before adding it: `systemd-run --user --pipe --wait -p <Property>=… /bin/sh -c 'grep -E "NoNewPrivs|Seccomp" /proc/self/status'`.

## Kill switch

```bash
touch ~/apps/agent-facts/ops/KILL     # next probe tick exits before its first request
rm ~/apps/agent-facts/ops/KILL
```

`AGENTFACTS_KILL=1` in a unit's environment does the same. The API keeps answering.

## Digest

```bash
.venv/bin/python ops/digest.py --dry-run             # last complete week, print only
.venv/bin/python ops/digest.py --dry-run --current   # this week so far
```

A real run writes `~/claude-hub/state/reviews/agent-facts-<date>.md`, a journal entry and (if
reported facts lack a probe) a card, commits them with `bin/state-commit --as agent-facts`, and
pings Telegram through the gateway (`send_telegram`, class `digest`, `X-Routine:
agent-facts-digest`). Publications stay "policy not approved" until `ops/publish-policy.yaml`
says `approved: true` (Edouard's tap).

## Caddy

`ops/Caddyfile.facts` is appended to `/etc/caddy/Caddyfile`. Check with `caddy adapt`, not `caddy
validate` (validate instantiates log files as root and breaks the next reload), then
`sudo systemctl reload caddy`. `facts.baillot.dev` resolves through the `*.baillot.dev` wildcard,
so the certificate comes on the first reload: `curl -s https://facts.baillot.dev/healthz`.
