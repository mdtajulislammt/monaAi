#!/usr/bin/env bash
# JARVIS Launcher Script
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$DIR/../venv/bin/python" ]; then
    exec "$DIR/../venv/bin/python" "$DIR/main.py" "$@"
else
    exec python "$DIR/main.py" "$@"
fi
