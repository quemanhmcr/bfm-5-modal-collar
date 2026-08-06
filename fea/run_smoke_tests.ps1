$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $python scripts\verify_environment.py
& $python scripts\validate_topology.py
& $python scripts\gmsh_smoke_test.py
& $python scripts\femm_smoke_test.py
& $python -m pytest -q
