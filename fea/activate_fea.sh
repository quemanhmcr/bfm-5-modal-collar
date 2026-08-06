#!/usr/bin/env bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/c/femm42/bin:/c/project/fea-tools/getdp-3.5.0/getdp-3.5.0-Windows64:$PATH"
source "$ROOT/.venv/Scripts/activate"
echo "BFM-5 FEA environment active: $VIRTUAL_ENV"
