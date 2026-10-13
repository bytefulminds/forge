# Builds the Forge Windows installer and smoke tests the app.
#
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
#
# Needs uv and Inno Setup 6 (https://jrsoftware.org/isinfo.php). ISCC.exe is
# looked up in the usual install folders; set $env:ISCC to use another one.
# Output: packaging\windows\Output\Forge-<version>-setup.exe

$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
$Root = (Get-Location).Path

# Native programs (uv, PyInstaller) write progress to stderr. Windows PowerShell
# turns that into errors when the output is redirected (as in CI), so they run
# with "Continue" and are judged by their exit code instead.
function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    $ErrorActionPreference = "Continue"
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

$ErrorActionPreference = "Continue"
$Version = (& uv run --frozen python scripts/release_notes.py --version 2>$null | Select-Object -Last 1)
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -ne 0 -or -not $Version) { throw "Could not read the version" }
$Version = $Version.Trim()
Write-Host "Building Forge $Version for Windows"

# --- Inno Setup ------------------------------------------------------------------
$IsccCandidates = @(
    $env:ISCC,
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }
if (-not $IsccCandidates) {
    throw "Inno Setup 6 (ISCC.exe) not found. Install it or set `$env:ISCC."
}
$Iscc = @($IsccCandidates)[0]

# --- freeze ------------------------------------------------------------------------
Invoke-Checked uv @("sync", "--frozen", "--extra", "web")
Invoke-Checked uv @("run", "--frozen", "python", "packaging/make_icons.py", "build/icons")
Invoke-Checked uv @("run", "--frozen", "pyinstaller", "--noconfirm", "--clean", "--log-level", "WARN", "packaging/forge.spec")

# --- smoke test ----------------------------------------------------------------------
# Forge.exe is a windowed program without a console: it writes its report to a file.
$Report = Join-Path $Root "build\smoke-windows.txt"
Remove-Item $Report -ErrorAction SilentlyContinue
$Smoke = Start-Process -FilePath "dist\Forge\Forge.exe" `
    -ArgumentList @("--smoke-test", "--smoke-report=$Report") -Wait -PassThru
if (Test-Path $Report) { Get-Content $Report | Write-Host }
if ($Smoke.ExitCode -ne 0) { throw "Smoke test failed (exit code $($Smoke.ExitCode))" }

# --- installer --------------------------------------------------------------------------
Invoke-Checked $Iscc @("/Qp", "/DAppVersion=$Version", "packaging\windows\forge.iss")
$Setup = "packaging\windows\Output\Forge-$Version-setup.exe"
if (-not (Test-Path $Setup)) { throw "$Setup was not created" }
$Size = [math]::Round((Get-Item $Setup).Length / 1MB)
Write-Host "Built $Setup ($Size MB)"
