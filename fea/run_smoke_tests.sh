#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PY='./.venv/Scripts/python.exe'
"$PY" scripts/verify_environment.py
"$PY" scripts/validate_topology.py
"$PY" scripts/gmsh_smoke_test.py
"$PY" scripts/femm_smoke_test.py
"$PY" -m pytest -q
