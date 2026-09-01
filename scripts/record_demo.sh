#!/bin/sh
# Record the terminal demonstrations in site/demo/tapes.
#
# The tapes run a real LocalSM against a throwaway home seeded from
# site/demo/scenario.yaml, the same scenario the simulated dashboard replays, so
# the recording and the demo show one machine. Nothing here reads or writes the
# operator's own configuration.
#
# The resulting GIFs are committed, because CI has no terminal to record in.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

if ! command -v vhs >/dev/null 2>&1; then
  echo "vhs is not installed; run 'brew install vhs' (it brings ttyd and ffmpeg)." >&2
  exit 1
fi

SANDBOX=$(mktemp -d "${TMPDIR:-/tmp}/localsm-cast.XXXXXX")
BIN="$SANDBOX/bin"
mkdir -p "$BIN"

cleanup() {
  # The tapes leave services running if a recording is interrupted.
  LOCALSM_CONFIG_DIR="$SANDBOX/config" LOCALSM_STATE_DIR="$SANDBOX/state" \
    "$ROOT/LocalSM" down >/dev/null 2>&1 || true
  rm -rf "$SANDBOX"
}
trap cleanup EXIT INT TERM

uv run python scripts/gen_demo_fixtures.py --seed "$SANDBOX" >/dev/null

cat > "$BIN/LocalSM" <<EOF
#!/bin/sh
exec "$ROOT/LocalSM" "\$@"
EOF
chmod +x "$BIN/LocalSM"

# ttyd inherits this environment, so the tapes need no setup of their own beyond
# clearing the screen. A plain prompt keeps the sandbox path out of the frame.
export PATH="$BIN:$PATH"
export LOCALSM_CONFIG_DIR="$SANDBOX/config"
export LOCALSM_STATE_DIR="$SANDBOX/state"
export LOCALSM_AGENTS_DIR="$SANDBOX/agents"
export PS1='$ '
export PROMPT_COMMAND=

# uv resolves the project on first use and says so; that belongs before the
# recording rather than in it.
LocalSM status >/dev/null 2>&1 || true

mkdir -p site/public/media
for tape in site/demo/tapes/*.tape; do
  echo "Recording $tape"
  vhs "$tape"
done

echo "Recorded into site/public/media."
