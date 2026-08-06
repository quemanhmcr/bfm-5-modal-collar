$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m pytest -q tests
Write-Host 'Local numerical smoke passed. FEMM smoke is remote-only via GitHub Actions.'
