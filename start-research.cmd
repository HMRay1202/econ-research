@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Econ Research

rem Windows launcher for Econ Research.
rem
rem Normal use:
rem   start-research.cmd
rem
rem Optional switches:
rem   --with-formula  Compatibility alias: formula OCR libraries are installed by default.
rem   --without-formula  Skip formula OCR library installation for a minimal setup.
rem   --setup-only    Validate/install the environment, then exit without starting the server.
rem   --no-open       Start the server without opening a browser.
rem   --stop          Stop this environment's server after confirmation.
rem
rem Long-running Conda and pip commands use --no-capture-output so progress remains visible.
rem Set ECON_RESEARCH_NO_PAUSE=1 to suppress the error pause in automated shells.

set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "APP_URL=http://127.0.0.1:8000/"
set "HEALTH_URL=%APP_URL%health"
set "UI_VERSION_URL=%APP_URL%api/ui-version"
set "CONDA_COMMAND="
set "EXPECTED_UI_VERSION="
set "DOWNLOAD_APPROVED=0"
set "INSTALL_FORMULA=1"
set "RUNTIME_OPTIONS="
set "SERVER_RUNNING=0"
set "SETUP_ONLY=0"
set "OPEN_BROWSER=1"
set "STOP_ONLY=0"

:parse_arguments
if "%~1"=="" goto :arguments_complete
if /I "%~1"=="--with-formula" (
  set "INSTALL_FORMULA=1"
) else if /I "%~1"=="--without-formula" (
  set "INSTALL_FORMULA=0"
) else if /I "%~1"=="--setup-only" (
  set "SETUP_ONLY=1"
) else if /I "%~1"=="--no-open" (
  set "OPEN_BROWSER=0"
) else if /I "%~1"=="--stop" (
  set "STOP_ONLY=1"
) else (
  call :fatal "Unknown option: %~1"
  exit /b 2
)
shift
goto :parse_arguments

:arguments_complete
if "%INSTALL_FORMULA%"=="0" set "RUNTIME_OPTIONS=--without-formula"
cd /d "%PROJECT_DIR%" || (
  call :fatal "Unable to open the project directory: %PROJECT_DIR%"
  exit /b 1
)

echo.
echo Econ Research Windows launcher
echo Project: %PROJECT_DIR%
echo.

call :find_conda
if errorlevel 1 (
  call :fatal "Conda was not found. Install Miniconda/Anaconda or run from Anaconda Prompt."
  exit /b 1
)
echo [1/6] Conda: %CONDA_COMMAND%
if "%STOP_ONLY%"=="1" goto :stop_existing_server

for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "$line = (Select-String -LiteralPath (Join-Path $env:PROJECT_DIR 'src\econ_research\api.py') -SimpleMatch 'WEB_UI_VERSION =').Line; if ($line) { ($line -split '=')[1].Trim().Trim([char]34) }"`) do set "EXPECTED_UI_VERSION=%%V"
if not defined EXPECTED_UI_VERSION (
  call :fatal "Could not read WEB_UI_VERSION from src\econ_research\api.py."
  exit /b 1
)

call :check_existing_server
if errorlevel 2 (
  call :fatal "Port 8000 belongs to another service or a different checkout. Stop it and retry."
  exit /b 1
)
if not errorlevel 1 (
  set "SERVER_RUNNING=1"
  echo Econ Research is already running; checking installed libraries without loading models.
)

echo [2/6] Checking the econ-research Conda environment...
call "%CONDA_COMMAND%" run -n econ-research python --version >nul 2>&1
if errorlevel 1 (
  echo The econ-research environment does not exist.
  call :confirm_download
  if errorlevel 2 exit /b 1
  if errorlevel 1 goto :cancelled
  echo.
  echo Creating the Conda environment. Progress will remain visible.
  call "%CONDA_COMMAND%" env create -f "%PROJECT_DIR%\environment.yml"
  if errorlevel 1 (
    call :fatal "Conda environment creation failed. Review the messages above."
    exit /b 1
  )
)
call "%CONDA_COMMAND%" run -n econ-research python --version
if errorlevel 1 (
  call :fatal "The econ-research environment exists but Python could not start."
  exit /b 1
)

echo.
echo [3/6] Checking the editable project installation...
call :editable_install_matches
if errorlevel 1 (
  echo The package is missing or points to a different project location.
  call :confirm_download
  if errorlevel 2 exit /b 1
  if errorlevel 1 goto :cancelled
  call :install_project
  if errorlevel 1 (
    call :fatal "Project installation failed. Review the pip messages above."
    exit /b 1
  )
) else (
  echo Editable installation points to this checkout.
)

rem Validate the hardware profile even when formula OCR was explicitly skipped.
(
  call :formula_dependencies_available
  if errorlevel 1 (
    echo.
    echo The selected CPU/GPU runtime is missing or cannot be used.
    echo Installing libraries only. Models are downloaded on the first actual recognition.
    call :confirm_download
    if errorlevel 2 exit /b 1
    if errorlevel 1 goto :cancelled
    call :install_formula_dependencies
    if errorlevel 1 (
      call :fatal "Optional formula OCR installation failed. The core app remains installed."
      exit /b 1
    )
    call :formula_dependencies_available
    if errorlevel 1 (
      call :fatal "Formula OCR import check failed after installation. Review the output above."
      exit /b 1
    )
  ) else (
    echo The selected CPU/GPU runtime is already available.
  )
)

echo.
echo [4/6] Running import and command smoke checks...
call "%CONDA_COMMAND%" run --no-capture-output -n econ-research python -c "import econ_research, fastapi, docling, uvicorn; print('Core imports: OK'); print('Package:', econ_research.__file__)"
if errorlevel 1 (
  call :fatal "Core dependency import check failed."
  exit /b 1
)
call "%CONDA_COMMAND%" run --no-capture-output -n econ-research research --help >nul 2>&1
if errorlevel 1 (
  call :fatal "The research command is not available after installation."
  exit /b 1
)

echo.
echo [5/6] Checking optional acceleration...
call "%CONDA_COMMAND%" run --no-capture-output -n econ-research python -c "import torch; print('PyTorch:', torch.__version__); print('PyTorch CUDA runtime:', torch.version.cuda); print('PyTorch CUDA available:', torch.cuda.is_available()); print('PyTorch GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU fallback')"
if errorlevel 1 echo Optional GPU diagnostics failed; the application can still use CPU fallbacks.

if "%SETUP_ONLY%"=="1" (
  echo.
  echo [6/6] Setup and validation completed successfully.
  exit /b 0
)

if "%SERVER_RUNNING%"=="1" (
  goto :existing_server_menu
)

:start_foreground
call :resolve_python
if errorlevel 1 goto :stop_failed
echo.
echo [6/6] Starting Econ Research at %APP_URL%
echo Keep this window open. Press Control-C to stop the server.
echo Server output will appear below.
echo.

if "%OPEN_BROWSER%"=="1" (
  start "Econ Research browser waiter" /b powershell -NoProfile -Command "$deadline = (Get-Date).AddSeconds(30); while ((Get-Date) -lt $deadline) { try { Invoke-WebRequest -UseBasicParsing -Uri '%HEALTH_URL%' -TimeoutSec 1 -ErrorAction Stop | Out-Null; Start-Process '%APP_URL%'; exit 0 } catch { Start-Sleep -Milliseconds 250 } }; Write-Warning 'The browser was not opened because the server did not become healthy within 30 seconds.'"
)

rem Run Python directly in this console so Ctrl+C reaches Uvicorn, not a Conda wrapper.
"%SERVER_PYTHON%" -u -m econ_research.cli serve --host 127.0.0.1 --port 8000
set "SERVER_EXIT=%ERRORLEVEL%"
if not "%SERVER_EXIT%"=="0" (
  call :fatal "The server stopped with exit code %SERVER_EXIT%."
  exit /b %SERVER_EXIT%
)
exit /b 0

:existing_server_menu
echo.
echo Econ Research is already running: %APP_URL%
echo Use Ctrl+C in its original server window for a graceful stop.
echo R/S terminate the verified server process; finish all work first.
echo [R] Stop and restart here  [S] Stop server  [L] View logs only  [Q] Quit
choice /c RSLQ /n /m "Choose R, S, L or Q: "
if errorlevel 5 exit /b 1
if errorlevel 4 exit /b 0
if errorlevel 3 goto :view_logs
if errorlevel 2 goto :stop_existing_server
call :stop_server
if errorlevel 1 goto :stop_failed
goto :start_foreground

:view_logs
if "%OPEN_BROWSER%"=="1" start "Econ Research browser" "%APP_URL%"
echo To stop the server separately, run stop-research.cmd.
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_DIR%\scripts\watch-server-logs.ps1" -ProjectDir "%PROJECT_DIR%"
exit /b 0

:stop_existing_server
call :stop_server
if errorlevel 1 goto :stop_failed
if /I not "%ECON_RESEARCH_NO_PAUSE%"=="1" pause
exit /b 0

:stop_failed
call :fatal "Server was not stopped. See the reason above."
exit /b 1

:stop_server
call :resolve_python
if errorlevel 1 exit /b 1
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_DIR%\scripts\stop-server.ps1" -ProjectDir "%PROJECT_DIR%" -PythonPath "%SERVER_PYTHON%"
exit /b %ERRORLEVEL%

:resolve_python
set "SERVER_PYTHON="
for /f "usebackq delims=" %%P in (`call "%CONDA_COMMAND%" run -n econ-research python -c "import sys; print(sys.executable)"`) do set "SERVER_PYTHON=%%P"
if not defined SERVER_PYTHON exit /b 1
if not exist "%SERVER_PYTHON%" exit /b 1
exit /b 0

:find_conda
if defined CONDA_EXE if exist "%CONDA_EXE%" set "CONDA_COMMAND=%CONDA_EXE%"
if not defined CONDA_COMMAND (
  for %%P in (
    "%USERPROFILE%\miniconda3\Scripts\conda.exe"
    "%USERPROFILE%\anaconda3\Scripts\conda.exe"
    "%USERPROFILE%\miniconda3\condabin\conda.bat"
    "%USERPROFILE%\anaconda3\condabin\conda.bat"
    "%ProgramData%\miniconda3\Scripts\conda.exe"
    "%ProgramData%\anaconda3\Scripts\conda.exe"
  ) do if not defined CONDA_COMMAND if exist "%%~fP" set "CONDA_COMMAND=%%~fP"
)
if not defined CONDA_COMMAND (
  for /f "delims=" %%P in ('where conda.exe 2^>nul') do if not defined CONDA_COMMAND set "CONDA_COMMAND=%%P"
)
if not defined CONDA_COMMAND (
  for /f "delims=" %%P in ('where conda.bat 2^>nul') do if not defined CONDA_COMMAND set "CONDA_COMMAND=%%P"
)
if not defined CONDA_COMMAND exit /b 1
exit /b 0

:check_existing_server
powershell -NoProfile -Command "try { $health = Invoke-WebRequest -UseBasicParsing -Uri '%HEALTH_URL%' -TimeoutSec 2 -ErrorAction Stop; $version = Invoke-WebRequest -UseBasicParsing -Uri '%UI_VERSION_URL%' -TimeoutSec 2 -ErrorAction Stop; if ($version.Content -like '*%EXPECTED_UI_VERSION%*') { exit 0 }; exit 2 } catch { if ($_.Exception.Response) { exit 2 }; exit 1 }" >nul 2>&1
exit /b %ERRORLEVEL%

:editable_install_matches
call "%CONDA_COMMAND%" run -n econ-research python -c "from pathlib import Path; import sys; import econ_research; expected = Path(sys.argv[1]).resolve() / 'src' / 'econ_research'; actual = Path(econ_research.__file__).resolve().parent; raise SystemExit(actual != expected)" "%PROJECT_DIR%" >nul 2>&1
exit /b %ERRORLEVEL%

:formula_dependencies_available
rem Model-free runtime checks. CUDA Paddle is checked only in its isolated worker.
call "%CONDA_COMMAND%" run --no-capture-output -n econ-research python "%PROJECT_DIR%\scripts\setup_runtime.py" %RUNTIME_OPTIONS%
exit /b %ERRORLEVEL%

:install_project
echo.
echo Installing libraries for the detected platform and hardware. Models are not downloaded.
call "%CONDA_COMMAND%" run --no-capture-output -n econ-research python "%PROJECT_DIR%\scripts\setup_runtime.py" --install %RUNTIME_OPTIONS%
exit /b %ERRORLEVEL%

:install_formula_dependencies
echo Installing optional formula OCR dependencies. Progress will remain visible.
call :install_project
exit /b %ERRORLEVEL%

:confirm_download
if "%SERVER_RUNNING%"=="1" (
  call :fatal "Stop the running Econ Research server before repairing its environment, then retry."
  exit /b 2
)
if "%DOWNLOAD_APPROVED%"=="1" exit /b 0
echo.
echo This step may download Conda or Python packages from the internet.
choice /c YN /n /m "Continue with download and installation? [Y/N] "
if errorlevel 3 (
  call :fatal "Could not read the installation choice. Run this script in an interactive terminal."
  exit /b 2
)
if errorlevel 2 exit /b 1
set "DOWNLOAD_APPROVED=1"
exit /b 0

:cancelled
echo.
echo Setup cancelled. No additional dependencies were requested.
exit /b 0

:fatal
echo.
echo ERROR: %~1
echo.
if /I not "%ECON_RESEARCH_NO_PAUSE%"=="1" (
  echo Press any key to close this window.
  pause >nul
)
exit /b 1
