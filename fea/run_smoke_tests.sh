#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m pytest -q tests
printf '%s\n' 'Local numerical smoke passed. FEMM smoke is remote-only via GitHub Actions.'
