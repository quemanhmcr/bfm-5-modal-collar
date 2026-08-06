$root = $PSScriptRoot
$env:Path = "C:\femm42\bin;C:\project\fea-tools\getdp-3.5.0\getdp-3.5.0-Windows64;$env:Path"
& "$root\.venv\Scripts\Activate.ps1"
Write-Host "BFM-5 FEA environment active: $env:VIRTUAL_ENV"
