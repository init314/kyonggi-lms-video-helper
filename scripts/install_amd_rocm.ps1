$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $ProjectRoot ".venv-rocm"
$Python = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    py -3.12 -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Python 3.12 is required. Install it from python.org first." }
}

$PythonVersion = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($PythonVersion -ne "3.12") {
    throw "AMD ROCm 7.2.1 PyTorch wheels require Python 3.12; found $PythonVersion in $Venv."
}

$RocmBase = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1"
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip." }

& $Python -m pip install --no-cache-dir `
    "$RocmBase/rocm_sdk_core-7.2.1-py3-none-win_amd64.whl" `
    "$RocmBase/rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl" `
    "$RocmBase/rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl" `
    "$RocmBase/rocm-7.2.1.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "Could not install AMD ROCm 7.2.1 runtime." }

& $Python -m pip install --no-cache-dir `
    "$RocmBase/torch-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl" `
    "$RocmBase/torchaudio-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl" `
    "$RocmBase/torchvision-0.24.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl"
if ($LASTEXITCODE -ne 0) { throw "Could not install AMD ROCm PyTorch." }

& $Python -m pip install -e "$($ProjectRoot)[build]"
if ($LASTEXITCODE -ne 0) { throw "Could not install project dependencies." }

& $Python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "Could not install Playwright Chromium." }

& $Python -c "import torch; assert torch.cuda.is_available(), 'ROCm GPU is unavailable'; print(torch.cuda.get_device_name(0)); print(torch.version.hip)"
if ($LASTEXITCODE -ne 0) { throw "PyTorch did not detect the AMD GPU." }

Write-Host "AMD GPU environment ready. Build with: .venv-rocm\Scripts\python.exe -m PyInstaller --noconfirm StudySsalmeok.spec"
