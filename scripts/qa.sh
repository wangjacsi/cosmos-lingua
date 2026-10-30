#!/usr/bin/env bash
# QA gate — `python -m pytest tests -q` with the cosmos core importable.
#
# Lingua imports `cosmos.core` from the cosmos checkout. Locate it the same way
# the README does: $COSMOS_SRC, else the sibling folder ../cosmos-billy. If that
# checkout has a venv, use its Python; otherwise expect `cosmos` to be installed
# in the current interpreter (CI does `pip install -e ../cosmos-billy[dev]`).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
COSMOS_SRC="${COSMOS_SRC:-$(pwd)/../cosmos-billy}"
if [ -x "$COSMOS_SRC/venv/bin/python" ]; then
  PY="$COSMOS_SRC/venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi
echo "python: $PY"
"$PY" -c 'import cosmos.core' 2>/dev/null || { echo "cosmos is not importable — set COSMOS_SRC or pip install -e <cosmos checkout>[dev]" >&2; exit 1; }
"$PY" -m pytest tests -q
echo "QA gate: PASS — $(git rev-parse --short HEAD)"
