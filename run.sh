#!/usr/bin/env bash
# Quick launcher script for monaAi Desktop Agent

set -e

SCRIPT_SOURCE="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
fi

source venv/bin/activate

# Terminate any lingering process on port 8765 to prevent Errno 98
fuser -k 8765/tcp 2>/dev/null || true
sleep 0.2

# Execute jarvis-core/main.py passing all arguments (defaults to Desktop HUD UI)
exec python jarvis-core/main.py "$@"
