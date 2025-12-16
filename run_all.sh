#!/bin/bash
# Convenience wrapper for run_all.py
# Usage: ./run_all.sh [options]

cd "$(dirname "$0")"
# Check for .venv
if [ -f ".venv/bin/python" ]; then
    PYTHON_CMD=".venv/bin/python"
else
    PYTHON_CMD="python3"
fi

$PYTHON_CMD scripts/run_all.py "$@"
