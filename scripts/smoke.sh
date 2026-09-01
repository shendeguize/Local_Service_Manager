#!/bin/sh
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
RUNNER="$ROOT/LocalSM"
PYTHON="${PYTHON:-python3}"
FAILURES=0
OLD_DSHC_PORT=""
OLD_DSHC_RUNNING=0
OLD_DSHC_LAUNCHD=0

step() {
  printf '\n$'
  printf ' %s' "$@"
  printf '\n'
  if "$@"; then
    printf 'PASS\n'
  else
    printf 'FAIL\n'
    FAILURES=$((FAILURES + 1))
  fi
}

capture_dshc_state() {
  command -v dshc >/dev/null 2>&1 || return 0
  OLD_DSHC_PORT=$(dshc config get manager.port 2>/dev/null || true)
  if dshc status >/dev/null 2>&1; then OLD_DSHC_RUNNING=1; fi
  if dshc service status 2>/dev/null | rg -q '加载：是|loaded|running'; then OLD_DSHC_LAUNCHD=1; fi
}

restore_dshc() {
  [ -n "$OLD_DSHC_PORT" ] || return 0
  printf '\nRestoring dshc manager state (port %s)\n' "$OLD_DSHC_PORT"
  if [ "$OLD_DSHC_RUNNING" -eq 1 ]; then
    current=$(dshc config get manager.port 2>/dev/null || true)
    if [ "$current" != "$OLD_DSHC_PORT" ]; then
      dshc up --port "$current" >/dev/null 2>&1 || true
      dshc config set manager.port "$OLD_DSHC_PORT" >/dev/null 2>&1 || true
      dshc restart --port "$current" >/dev/null 2>&1 || dshc up --port "$OLD_DSHC_PORT" >/dev/null 2>&1 || true
    fi
    if [ "$OLD_DSHC_LAUNCHD" -eq 1 ]; then
      dshc service uninstall >/dev/null 2>&1 || true
      dshc service install >/dev/null 2>&1 || true
    fi
  else
    dshc down >/dev/null 2>&1 || true
  fi
}

cleanup() {
  "$RUNNER" down >/dev/null 2>&1 || true
  "$RUNNER" tunnel rm smoke >/dev/null 2>&1 || true
  restore_dshc
}
trap cleanup EXIT INT TERM

printf 'LocalSM full smoke\n'

# The service list comes from the machine-readable config contract rather than
# a hardcoded list, so this script exercises whatever the operator configured.
SERVICES=$("$RUNNER" --json config 2>/dev/null | "$PYTHON" -c \
  'import json,sys; print(" ".join(s["name"] for s in json.load(sys.stdin)["services"] if s["name"] != "web"))' \
  2>/dev/null) || SERVICES=""
if [ -z "$SERVICES" ]; then
  printf 'FAIL: no services configured. Run `LocalSM init` and define services first.\n'
  exit 1
fi
printf 'Services under test: %s\n' "$SERVICES"

capture_dshc_state

port=19000
for service in $SERVICES; do
  port=$((port + 1))
  target=$((port + 100))
  if [ "$service" = "dshc" ] && [ -n "$OLD_DSHC_PORT" ] && [ "$OLD_DSHC_RUNNING" -eq 0 ]; then
    step dshc up --port "$OLD_DSHC_PORT"
  fi
  step "$RUNNER" up "$service" --port "$port"
  step "$RUNNER" status "$service"
  step "$RUNNER" set-port "$service" "$target"
  step "$RUNNER" restart "$service"
  step "$RUNNER" down "$service"
done

printf '\nRemote scan\n'
step "$RUNNER" remote scan --timeout "${LOCALSM_SSH_TIMEOUT:-8}"

printf '\nTunnel lifecycle\n'
SMOKE_HOST="${LOCALSM_SMOKE_HOST:-}"
if [ -z "$SMOKE_HOST" ]; then
  SMOKE_HOST=$(awk 'tolower($1) == "host" && $2 !~ /[*?!]/ {print $2; exit}' "$HOME/.ssh/config" 2>/dev/null || true)
fi
if [ -n "$SMOKE_HOST" ]; then
  TUNNEL_ADD=$("$RUNNER" --json tunnel add smoke "$SMOKE_HOST" 19222 22 2>&1) || {
    printf '%s\n' "$TUNNEL_ADD"
    FAILURES=$((FAILURES + 1))
    TUNNEL_ADD=""
  }
  if [ -n "$TUNNEL_ADD" ]; then
    printf '%s\n' "$TUNNEL_ADD"
    step "$PYTHON" -c 'import socket; socket.create_connection(("127.0.0.1", 19222), 5).close()'
    TUNNEL_PID=$(printf '%s\n' "$TUNNEL_ADD" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["pid"])')
    step "$PYTHON" -c "import os,signal; os.killpg($TUNNEL_PID, signal.SIGTERM)"
    step "$RUNNER" tunnel ensure smoke
    step "$RUNNER" tunnel rm smoke
  fi
else
  printf 'WARN: no SSH Host available for tunnel smoke\n'
fi

printf '\nWeb and doctor\n'
step "$RUNNER" web
step "$PYTHON" -c 'import urllib.request; assert urllib.request.urlopen("http://127.0.0.1:8765/", timeout=5).status == 200'
step "$PYTHON" -c 'import urllib.request; assert urllib.request.urlopen("http://127.0.0.1:8765/static/app.js", timeout=5).status == 200'
step "$RUNNER" doctor --local-only

if [ "$FAILURES" -eq 0 ]; then
  printf '\nSMOKE PASS\n'
else
  printf '\nSMOKE FAIL: %s step(s)\n' "$FAILURES"
fi
exit "$FAILURES"
