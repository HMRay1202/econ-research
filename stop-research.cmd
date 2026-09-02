@echo off
rem Stop only the verified Econ Research server on port 8000, after confirmation.
call "%~dp0start-research.cmd" --stop
exit /b %ERRORLEVEL%
