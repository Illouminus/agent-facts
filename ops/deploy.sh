#!/usr/bin/env bash
# ops/deploy.sh — host side of "merge = deployed" for agent-facts on illouminus (spec 08, W8).
#
# Reached from GitHub Actions ONLY through a forced command (ops/README.md):
#   command="/home/ubuntu/apps/agent-facts/ops/deploy.sh",restrict ssh-ed25519 AAAA… gha-deploy-agent-facts
# The client's string lands in $SSH_ORIGINAL_COMMAND and is untrusted input: exactly one 40-hex
# sha that is on origin/main and not behind the deployed one is accepted, nothing else. By hand:
# ops/deploy.sh <sha> (any sha on origin/main, so a rollback is possible).
#
# Steps: fetch → the sha must be on origin/main → keep the probe runner's uncommitted edits under
# facts/ as a patch → checkout --detach <sha> → re-apply the patch (if it no longer applies it is
# parked in var/deploy/facts-unapplied-*.patch, never lost) → uv sync --frozen --no-dev →
# when ops/systemd/ changed: link unit files not yet linked, daemon-reload (enabling a new unit
# stays a deliberate step) → restart agentfacts-api → poll /healthz. Failure → the same steps back
# to the previous sha, exit 1: a red deploy means "prod alive on the old version". Success →
# var/deploy/deployed + ops/state_journal.py --prev, which writes a megabrain journal entry only
# when the registry's substance changed (its failure is logged and never fails the deploy).
#
# Everything runs inside main(): bash has parsed the whole body before `git checkout` replaces this
# file. `restrict` means no profile is sourced, hence the pinned PATH. Must also run under macOS
# bash 3.2 (tests/ops/test_deploy_sh.py): no mapfile, no [[ =~ ]], flock only when present.
#
# Exit: 0 deployed (or already deployed and healthy), 1 failed and rolled back, 2 refused input,
#       3 failed and the rollback failed too (prod down), 75 another deploy is running.

main() {
  set -uo pipefail
  export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  local app deploy_dir sha prev
  app="$(cd "$(dirname "$0")/.." && pwd -P)"
  deploy_dir="$app/var/deploy"
  HEALTH_URL="${AGENTFACTS_HEALTH_URL:-http://127.0.0.1:8795/healthz}"
  HEALTH_TRIES="${AGENTFACTS_HEALTH_TRIES:-20}"
  HEALTH_SLEEP="${AGENTFACTS_HEALTH_SLEEP:-1}"
  STATE_DIR="$HOME/claude-hub/state"
  mkdir -p "$deploy_dir" || { echo "deploy: cannot create $deploy_dir" >&2; return 1; }
  LOG="$deploy_dir/deploy.log"

  sha="${SSH_ORIGINAL_COMMAND:-${1:-}}"
  case "$sha" in
    *[!0-9a-f]* | "") refuse "expected one 40-hex sha, got ${#sha} characters that are not all hex"; return 2 ;;
  esac
  [ "${#sha}" -eq 40 ] || { refuse "expected one 40-hex sha, got ${#sha} characters"; return 2; }

  exec 9>"$deploy_dir/lock"
  if command -v flock >/dev/null 2>&1 && ! flock -n 9; then
    log "busy: another deploy holds $deploy_dir/lock"
    return 75
  fi
  # The probe runner's tick lock (var/probe.lock, fcntl.flock): a tick writes facts/ — wait for it
  # to finish so the checkout neither loses its edits nor swaps code under a running tick. A tick
  # that starts meanwhile sees the lock busy and exits quietly.
  exec 8>>"$app/var/probe.lock"
  if command -v flock >/dev/null 2>&1 && ! flock -w "${AGENTFACTS_PROBE_LOCK_WAIT:-900}" 8; then
    log "busy: a probe tick still holds var/probe.lock; nothing changed"
    return 75
  fi

  cd "$app" || return 1
  # The repo is public: fetch anonymously, never through the owner's `gh auth git-credential`
  # helper in ~/.gitconfig (sec card 2026-10-23, D-089).
  if ! GIT_TERMINAL_PROMPT=0 git -c credential.helper= fetch --quiet origin main 2>>"$LOG"; then
    log "git fetch origin main failed (see $LOG); nothing changed"
    return 1
  fi
  if ! git cat-file -e "$sha^{commit}" 2>/dev/null; then
    refuse "$sha is not on origin/main (unknown commit)"
    return 2
  fi
  if ! git merge-base --is-ancestor "$sha" origin/main; then
    refuse "$sha is not on origin/main"
    return 2
  fi
  prev="$(git rev-parse HEAD)"
  # Over ssh only forward: a leaked Actions key must not buy a downgrade to an old main commit.
  # Rolling back to an earlier sha stays a by-hand act (no SSH_ORIGINAL_COMMAND).
  if [ -n "${SSH_ORIGINAL_COMMAND:-}" ] && ! git merge-base --is-ancestor "$prev" "$sha"; then
    refuse "$sha is not ahead of the deployed $prev (downgrade over ssh); roll back by hand"
    return 2
  fi

  if [ "$prev" = "$sha" ] && healthy; then
    log "already deployed and healthy: $sha"
    return 0
  fi

  log "deploying $sha (was $prev)"
  if switch "$prev" "$sha"; then
    printf '%s\n' "$sha" >"$deploy_dir/deployed"
    log "deployed $sha, /healthz ok"
    journal "$app" "$sha" "$prev"
    return 0
  fi
  log "release $sha unhealthy or failed; rolling back to $prev"
  if switch "$sha" "$prev"; then
    log "rolled back to $prev, /healthz ok; $sha is NOT deployed"
    return 1
  fi
  log "ROLLBACK FAILED: prod is down (HEAD $(git rev-parse --short HEAD))"
  return 3
}

log() {
  local line
  line="$(date -u +%Y-%m-%dT%H:%M:%SZ) deploy: $*"
  printf '%s\n' "$line"
  printf '%s\n' "$line" >>"$LOG" 2>/dev/null || true
}

refuse() {
  log "REFUSED: $*"
}

healthy() {
  local i=0 body
  while [ "$i" -lt "$HEALTH_TRIES" ]; do
    if body="$(curl -fsS -m 3 "$HEALTH_URL" 2>/dev/null)"; then
      case "$body" in *'"ok":true'*) return 0 ;; esac
    fi
    i=$((i + 1))
    [ "$i" -lt "$HEALTH_TRIES" ] && sleep "$HEALTH_SLEEP"
  done
  return 1
}

# switch <from> <to>: carry facts/ edits, check out, sync, reload units if needed, restart, health.
switch() {
  local from="$1" to="$2" patch parked
  patch="$(dirname "$LOG")/facts-carry.patch"
  # untracked files under facts/ (bot drafts) go into the patch too: intent-to-add first
  git ls-files -z --others --exclude-standard -- facts | xargs -0 git add -N -- 2>/dev/null
  git diff --binary HEAD -- facts >"$patch" || return 1
  if ! git checkout --quiet --force --detach "$to"; then
    log "git checkout $to failed"
    return 1
  fi
  if [ -s "$patch" ]; then
    if git apply --check "$patch" 2>/dev/null && git apply "$patch"; then
      log "carried uncommitted facts/ edits across the checkout"
    elif git apply --reverse --check "$patch" 2>/dev/null; then
      log "uncommitted facts/ edits are already in $to (bot PR merged); dropped the copy"
    else
      parked="$(dirname "$LOG")/facts-unapplied-$(date -u +%Y%m%dT%H%M%SZ).patch"
      mv "$patch" "$parked"
      log "WARN: uncommitted facts/ edits conflict with $to; parked in $parked"
    fi
  fi
  rm -f "$patch"
  if ! uv sync --frozen --no-dev --quiet >>"$LOG" 2>&1; then
    log "uv sync failed (see $LOG)"
    return 1
  fi
  if ! git diff --quiet "$from" "$to" -- ops/systemd; then
    link_new_units || return 1
    systemctl --user daemon-reload || { log "daemon-reload failed"; return 1; }
  fi
  if ! systemctl --user restart agentfacts-api.service; then
    log "restart agentfacts-api.service failed"
    return 1
  fi
  healthy || { log "/healthz not ok after $HEALTH_TRIES tries"; return 1; }
}

# A unit file new in ops/systemd/ gets `systemctl --user link`ed (the others are links already).
link_new_units() {
  local unit name dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  for unit in "$PWD"/ops/systemd/agentfacts-*; do
    [ -f "$unit" ] || continue
    name="$(basename "$unit")"
    [ -e "$dir/$name" ] || [ -L "$dir/$name" ] && continue
    if ! systemctl --user link "$unit" >>"$LOG" 2>&1; then
      log "systemctl --user link $name failed"
      return 1
    fi
    log "linked new unit $name (enable it by hand: ops/README.md)"
  done
}

journal() {
  local app="$1" sha="$2" prev="$3" subject
  if [ ! -x "$app/.venv/bin/python" ] || [ ! -d "$STATE_DIR" ]; then
    log "journal hook skipped (no .venv or no $STATE_DIR)"
    return 0
  fi
  subject="$(git log -1 --format=%s "$sha")"
  if ! "$app/.venv/bin/python" "$app/ops/state_journal.py" --sha "$sha" --prev "$prev" \
      --subject "$subject" --root "$app" --state-dir "$STATE_DIR" >>"$LOG" 2>&1; then
    log "WARN: journal hook failed (deploy is fine; see $LOG)"
  fi
}

main "$@"
exit $?
