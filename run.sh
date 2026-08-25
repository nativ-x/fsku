#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PYTHON_BIN="$(which python3 || which python || echo "python")"

if [ "$1" == "sync" ]; then
    "$PYTHON_BIN" fsku_cli.py sync "${@:2}"
elif [ "$1" == "forward" ]; then
    "$PYTHON_BIN" fsku_cli.py forward "${@:2}"
elif [ "$1" == "list" ]; then
    "$PYTHON_BIN" fsku_cli.py list "${@:2}"
elif [ "$1" == "stats" ]; then
    "$PYTHON_BIN" fsku_cli.py stats "${@:2}"
elif [ "$1" == "test" ]; then
    "$PYTHON_BIN" -m pytest tests/
else
    echo "Starting FSKU Platform..."
    "$PYTHON_BIN" fsku_cli.py serve --host 0.0.0.0 --port 8000
fi
