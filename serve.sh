#!/usr/bin/env bash
# serve.sh — launch the Cyclops brain + companion web dashboard.
#
# Starts the stdlib web dashboard (app/server.py) which also hosts the
# brain pipeline (transcription + smart-note extraction) and the JSON API.
# When /home/gio/ai_api.txt (or ~/.env) provides keys, the pipeline
# automatically upgrades to cloud transcription + LLM note extraction.
#
# Usage:
#   ./serve.sh                 # serve on default port 8080
#   ./serve.sh --port 9090     # custom port
#   ./serve.sh --dry-run       # show config + what would launch, no server
#   ./serve.sh --check         # verify env/keys/venv, exit 0/1
#
# The script is venv-aware: if a Python venv lives at ~/cyclops-venv or
# /home/gio/.venvs/cyclops it is activated automatically.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# allow running from anywhere: if this script is inside the repo use it,
# otherwise fall back to the known healthy location.
if [[ ! -f "$REPO_DIR/app/server.py" ]]; then
  REPO_DIR="/home/gio/cyclops"
fi

PORT=8080
DRY_RUN=0
CHECK_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    --check) CHECK_ONLY=1; shift;;
    -h|--help) sed -n '2,18p' "$0"; exit 0;;
    *) echo "unknown arg: $1" >&2; exit 1;;
  esac
done

echo "== Cyclops serve =="
echo "repo: $REPO_DIR"

# --- venv detection -------------------------------------------------------
VENV=""
for c in "$REPO_DIR/.venv" "$HOME/cyclops-venv" "/home/gio/.venvs/cyclops"; do
  if [[ -x "$c/bin/activate" ]]; then VENV="$c"; break; fi
done
if [[ -n "$VENV" ]]; then
  echo "venv: $VENV"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
else
  echo "venv: (none — using system python: $(command -v python3))"
fi

# --- AI-stack check -------------------------------------------------------
AI_TXT="${CYCLOPS_AI_API_TXT:-/home/gio/ai_api.txt}"
if [[ -f "$AI_TXT" ]]; then
  echo "ai keys: $AI_TXT ($(grep -c ':' "$AI_TXT" 2>/dev/null || echo 0) entries)"
else
  echo "ai keys: (not found at $AI_TXT — pipeline will use local stub/rule engine)"
fi

# show which providers look configured
if python3 - <<'PY' 2>/dev/null
import sys; sys.path.insert(0, "$REPO_DIR")
try:
    from brain.aikeys import AiKeys
    k = AiKeys()
    av = k.available()
    print("configured providers:", ", ".join(av) if av else "(none)")
except Exception as e:
    print("aikeys check skipped:", e)
PY
then :; fi

if [[ $CHECK_ONLY -eq 1 ]]; then
  echo "check complete."
  exit 0
fi

# --- launch ---------------------------------------------------------------
CMD=(python3 "$REPO_DIR/app/server.py" "$PORT")
echo "launch: ${CMD[*]}"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "(dry-run — not starting server)"
  exit 0
fi

cd "$REPO_DIR"
exec "${CMD[@]}"
