@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Agent maintenance notes (Windows)
rem - This launcher must be run from the repository root; %%~dp0 makes project paths move-safe.
rem - It never downloads packages without a Y confirmation. Keep that prompt before both
rem   "conda env create" and editable pip repair paths.
rem - "PyTorch CUDA available: True" means Docling's standard AUTO pipeline may use NVIDIA CUDA.
rem   "Paddle compiled with CUDA: False" is expected from the default CPU Paddle dependency.
rem - The experimental ECON_RESEARCH_FORMULA_ENRICHMENT path is Apple-MPS-specific; do not enable
rem   it for Windows CUDA debugging. Formula OCR otherwise falls back safely to CPU/Docling text.
rem - On a Windows bug report, collect: `nvidia-smi`, this launcher's CUDA lines, and
rem   `conda run -n econ-research pytest`. Do not commit .env, data/, PDFs, or databases.

set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "APP_URL=http://127.0.0.1:8000/"
set "HEALTH_URL=%APP_URL%health"
set "UI_VERSION=2026-08-27-formula-v2"
set "UI_VERSION_URL=%APP_URL%api/ui-version"
set "CONDA_COMMAND="
set "DOWNLOAD_APPROVED=0"

cd /d "%PROJECT_DIR%" || (
  echo Unable to open the project directory: %PROJECT_DIR%
  exit /b 1
)

if defined CONDA_EXE if exist "%CONDA_EXE%" set "CONDA_COMMAND=%CONDA_EXE%"
if not defined CONDA_COMMAND (
  for %%P in (
    "%USERPROFILE%\anaconda3\condabin\conda.bat"
    "%USERPROFILE%\miniconda3\condabin\conda.bat"
    "%ProgramData%\anaconda3\condabin\conda.bat"
  ) do if not defined CONDA_COMMAND if exist "%%~fP" set "CONDA_COMMAND=%%~fP"
)
if not defined CONDA_COMMAND (
  for /f "delims=" %%P in ('where conda 2^>nul') do if not defined CONDA_COMMAND set "CONDA_COMMAND=%%P"
)
if not defined CONDA_COMMAND (
  echo Conda was not found. Install Conda, or run this script from Anaconda Prompt.
  echo Project directory: %PROJECT_DIR%
  exit /b 1
)

powershell -NoProfile -Command "$health = Invoke-WebRequest -UseBasicParsing -Uri '%HEALTH_URL%' -TimeoutSec 2 -ErrorAction SilentlyContinue; if ($health) { $version = Invoke-WebRequest -UseBasicParsing -Uri '%UI_VERSION_URL%' -TimeoutSec 2 -ErrorAction SilentlyContinue; if ($version -and $version.Content -like '*%UI_VERSION%*') { exit 0 }; exit 2 }; exit 1" >nul 2>&1
if errorlevel 2 goto :port_conflict
if not errorlevel 1 goto :already_running

call "%CONDA_COMMAND%" run -n econ-research python --version >nul 2>&1
if errorlevel 1 (
  echo The econ-research Conda environment was not found.
  call :confirm_download
  if errorlevel 1 (
    echo Setup cancelled. No environment or dependencies were downloaded.
    exit /b 0
  )
  call "%CONDA_COMMAND%" env create -f environment.yml
  if errorlevel 1 (
    echo Conda environment creation failed. Review the output above.
    exit /b 1
  )
)

call "%CONDA_COMMAND%" run -n econ-research python -c "from pathlib import Path; import sys; import econ_research; expected = Path(sys.argv[1]).resolve() / 'src' / 'econ_research'; actual = Path(econ_research.__file__).resolve().parent; raise SystemExit(actual != expected)" "%PROJECT_DIR%" >nul 2>&1
if errorlevel 1 (
  echo econ_research is missing or points to an older project location. Repairing the editable installation...
  call :confirm_download
  if errorlevel 1 (
    echo Setup cancelled. No dependencies were downloaded.
    exit /b 0
  )
  call "%CONDA_COMMAND%" run -n econ-research python -m pip install -e ".[dev,formula]"
  if errorlevel 1 (
    echo Editable installation repair failed. Review the pip output above.
    exit /b 1
  )
)

echo Checking optional GPU acceleration...
call "%CONDA_COMMAND%" run -n econ-research python -c "import torch; import paddle; print('PyTorch CUDA available:', torch.cuda.is_available()); print('Paddle compiled with CUDA:', paddle.is_compiled_with_cuda()); print('Paddle device:', paddle.device.get_device())"
if errorlevel 1 echo GPU diagnostics were unavailable; the application will continue with CPU fallbacks.

start "Econ Research browser" /b powershell -NoProfile -Command "$deadline = (Get-Date).AddSeconds(20); while ((Get-Date) -lt $deadline) { try { $health = Invoke-WebRequest -UseBasicParsing -Uri '%HEALTH_URL%' -TimeoutSec 1 -ErrorAction Stop; Start-Process '%APP_URL%'; exit 0 } catch { Start-Sleep -Milliseconds 250 } }"

echo Starting Econ Research...
echo Close this window or press Control-C to stop the server.
call "%CONDA_COMMAND%" run --no-capture-output -n econ-research research serve --host 127.0.0.1 --port 8000
exit /b %errorlevel%

:already_running
echo Econ Research is already running: %APP_URL%
start "Econ Research browser" "%APP_URL%"
exit /b 0

:port_conflict
echo Port 8000 is already used by an older version or another service.
echo Stop that service, then run this launcher again.
exit /b 1

:confirm_download
if "%DOWNLOAD_APPROVED%"=="1" exit /b 0
echo.
echo Creating the environment or repairing this installation may download Conda and Python packages.
choice /c YN /n /m "Download and install the required packages now"
if errorlevel 2 exit /b 1
set "DOWNLOAD_APPROVED=1"
exit /b 0
