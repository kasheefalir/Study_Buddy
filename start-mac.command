#!/bin/bash
set -e
cd "$(dirname "$0")"

if [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python -m app.launch
fi
exec python3 -m app.launch
