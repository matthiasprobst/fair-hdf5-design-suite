#!/usr/bin/env bash
# Build the frontend and serve the complete app through the local Python API.
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'HELP'
Usage: ./start.sh

Creates .venv when needed, installs Python dependencies, installs frontend
packages when needed, builds the UI and starts the full app at:
  http://127.0.0.1:8000

Requires Python 3.10+, Node.js 20+ and npm. The first start needs internet access.
Press Ctrl+C to stop the app. Run from any directory using the script's path.
HELP
  exit 0
fi
if (( $# > 0 )); then
  printf 'Unknown argument: %s\nUse --help for usage.\n' "$1" >&2
  exit 2
fi

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
for executable in python3 node npm; do
  if ! command -v "$executable" >/dev/null 2>&1; then
    printf 'Missing prerequisite: %s. See README.md for local setup.\n' "$executable" >&2
    exit 1
  fi
done
python3 -c 'import sys; sys.exit("Python 3.10+ is required.") if sys.version_info < (3, 10) else None'
node -e 'if (Number(process.versions.node.split(".")[0]) < 20) { console.error("Node.js 20+ is required."); process.exit(1); }'

if [[ ! -x .venv/bin/python ]]; then
  printf 'Creating Python virtual environment…\n'
  python3 -m venv .venv
fi

# Fail before installation/build if the API port is already occupied.
.venv/bin/python - <<'PY'
import socket
import sys
with socket.socket() as probe:
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(('127.0.0.1', 8000))
    except OSError as error:
        sys.exit(f'Cannot start on 127.0.0.1:8000: {error}. Stop the existing server and retry.')
PY

printf 'Checking Python dependencies…\n'
.venv/bin/python -m pip install -r requirements.txt
if [[ ! -x frontend/node_modules/.bin/vite || ! -f frontend/node_modules/.package-lock.json || frontend/package-lock.json -nt frontend/node_modules/.package-lock.json ]]; then
  printf 'Installing frontend dependencies…\n'
  npm ci --prefix frontend
fi
printf 'Building frontend…\n'
npm run build --prefix frontend
printf '\nStarting FAIR HDF5 Design Suite at http://127.0.0.1:8000\nPress Ctrl+C to stop.\n\n'
exec .venv/bin/python app.py
