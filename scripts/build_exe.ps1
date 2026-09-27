$ErrorActionPreference = "Stop"


$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$SpecFile = Join-Path $ProjectRoot "StudySsalmeok.spec"


if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment not found. Create it with: python -m venv .venv"
}


& $Python -m PyInstaller --clean --noconfirm $SpecFile


if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}


Write-Host "Built: dist\StudySsalmeok\StudySsalmeok.exe"
