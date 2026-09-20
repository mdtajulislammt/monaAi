#!/usr/bin/env bash
# Quick launcher script for monaAi Desktop Agent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
fi

source venv/bin/activate

# Execute main.py passing all arguments (defaults to Desktop Web UI)
python main.py "$@"
