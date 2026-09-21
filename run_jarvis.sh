#!/usr/bin/env bash
# JARVIS Launcher Script
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
exec ./venv/bin/python jarvis-core/main.py "$@"
