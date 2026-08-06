$ErrorActionPreference = 'Stop'
$Url = 'https://www.femm.info/doku/lib/exe/fetch.php?media=upload%3Afiles%3Afemm42bin_x64_21apr2019.exe'
$ExpectedSha256 = '17384e8990b6305ec8ffef1f75b6ef091a266b6e49b30c151cd1daca2e952043'
$Installer = Join-Path $env:RUNNER_TEMP 'femm42bin_x64_21Apr2019.exe'
$InstallDir = 'C:\femm42'

if (-not (Test-Path $Installer)) {
    Invoke-WebRequest -Uri $Url -OutFile $Installer -MaximumRetryCount 4 -RetryIntervalSec 5
}
$Actual = (Get-FileHash -Path $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Actual -ne $ExpectedSha256) {
    throw "FEMM installer SHA-256 mismatch: $Actual"
}

$Exe = Join-Path $InstallDir 'bin\femm.exe'
if (-not (Test-Path $Exe)) {
    $arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=$InstallDir")
    $process = Start-Process -FilePath $Installer -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "FEMM installer failed with exit code $($process.ExitCode)"
    }
}
if (-not (Test-Path $Exe)) {
    throw "FEMM executable not found at $Exe"
}

$Bin = Split-Path $Exe
$Bin | Out-File -FilePath $env:GITHUB_PATH -Encoding utf8 -Append
"FEMM_EXE=$Exe" | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
"FEMM_INSTALLER_SHA256=$ExpectedSha256" | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
Write-Host "FEMM installed and verified: $Exe"
