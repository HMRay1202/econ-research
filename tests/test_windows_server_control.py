import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell process-control mocks")
@pytest.mark.parametrize("scenario", ["stop", "check", "other", "busy", "reused", "cancel"])
def test_stop_helper_only_terminates_verified_idle_server(scenario):
    # Mock every process/network operation: never inspect or stop a real server in this test.
    script = r'''
$script:stopped = $false
$script:queries = 0
function Get-NetTCPConnection {
    if (-not $script:stopped) { [pscustomobject]@{LocalPort=8000;OwningProcess=12345} }
}
function Get-CimInstance {
    $script:queries++
    $exe = $env:TEST_PYTHON
    if ($env:TEST_CASE -eq 'other') { $exe = 'C:\unrelated\python.exe' }
    $created = 10
    if ($env:TEST_CASE -eq 'reused' -and $script:queries -gt 1) { $created = 20 }
    [pscustomobject]@{
        ExecutablePath=$exe; CreationDate=$created
        CommandLine=('"' + $env:TEST_PYTHON + '" -u -m econ_research.cli serve --port 8000')
    }
}
function Invoke-RestMethod {
    param($Uri, $TimeoutSec)
    if ($Uri -like '*/health') { return @{status='ok'} }
    if ($env:TEST_CASE -eq 'busy') { return ,@{status='running'} }
    return @()
}
function Stop-Process { param($Id, $ErrorAction); $script:stopped=$true; Write-Host "STOPPED:$Id" }
function Wait-Process { param($Id, $Timeout, $ErrorAction) }
function Read-Host { return 'NO' }
& $env:TEST_SCRIPT -ProjectDir $env:TEST_ROOT -PythonPath $env:TEST_PYTHON `
    -Confirmed:($env:TEST_CASE -ne 'cancel') -CheckOnly:($env:TEST_CASE -eq 'check')
'''
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        env={**os.environ, "TEST_PYTHON": sys.executable, "TEST_ROOT": str(ROOT),
             "TEST_SCRIPT": str(ROOT / "scripts/stop-server.ps1"), "TEST_CASE": scenario},
        capture_output=True, timeout=20,
    )
    if scenario == "stop":
        assert result.returncode == 0, result.stderr
        assert b"STOPPED:12345" in result.stdout
    else:
        assert b"STOPPED:" not in result.stdout
        assert result.returncode == (0 if scenario == "check" else 1), result.stdout
