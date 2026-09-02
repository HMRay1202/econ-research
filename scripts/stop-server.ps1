[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ProjectDir,
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [switch]$Confirmed,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
try {
    $expectedPython = (Resolve-Path -LiteralPath $PythonPath).Path
    $expectedPackage = Join-Path (Resolve-Path -LiteralPath $ProjectDir).Path 'src\econ_research'
    $actualPackage = & $expectedPython -c 'import econ_research,pathlib; print(pathlib.Path(econ_research.__file__).resolve().parent)'
    if ($LASTEXITCODE -ne 0 -or $actualPackage -ne $expectedPackage) {
        throw 'The environment does not point to this checkout; refusing to stop anything.'
    }
    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
        Where-Object { $_.LocalPort -eq 8000 })
    if ($listeners.Count -eq 0) { Write-Host 'No server is listening on port 8000.'; exit 0 }
    $serverIds = @($listeners.OwningProcess | Select-Object -Unique)
    if ($serverIds.Count -ne 1) { throw 'Ambiguous port ownership; refusing to stop anything.' }
    $serverId = $serverIds[0]
    $server = Get-CimInstance Win32_Process -Filter "ProcessId=$serverId"
    # No name-wide kill and no process-tree kill. Match the precise environment and serve command.
    $entrypoint = Join-Path (Split-Path $expectedPython -Parent) 'Scripts\research.exe'
    $command = $server.CommandLine
    if ($server.ExecutablePath -ne $expectedPython -or
        -not ($command -match ('(?i)"' + [regex]::Escape($entrypoint) + '"\s+serve(?:\s|$)') -or
              $command -match '(?i)\s-m\s+econ_research\.cli\s+serve(?:\s|$)') -or
        $command -match '(?i)\s--reload(?:\s|$)') {
        throw 'Port 8000 is not owned by a recognized non-reload Econ Research server.'
    }
    $health = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 3
    if ($health.status -ne 'ok') { throw 'Server identity/health check failed.' }
    $jobs = Invoke-RestMethod 'http://127.0.0.1:8000/api/uploads?active_only=true' -TimeoutSec 3
    if ($null -ne $jobs -and $jobs.Count -gt 0) {
        throw 'Uploads are queued/running. Wait for them to finish before stopping the server.'
    }
    Write-Host "Verified server PID $serverId ($expectedPython). No active upload jobs."
    if ($CheckOnly) { exit 0 }
    if (-not $Confirmed) {
        Write-Warning 'This TERMINATES the process. Finish any reparse/card/deep-read requests first.'
        Write-Host 'For a graceful shutdown use Ctrl+C in the original server terminal instead.'
        if ((Read-Host 'Terminate this server? Type STOP to confirm') -cne 'STOP') {
            Write-Host 'Cancelled; the server is unchanged.'
            exit 1
        }
    }
    # Revalidate PID creation time and port ownership after the user prompt (PID reuse protection).
    $current = Get-CimInstance Win32_Process -Filter "ProcessId=$serverId"
    if ($null -eq $current -or $current.CreationDate -ne $server.CreationDate -or
        $current.CommandLine -ne $command) { throw 'Server identity changed; retry.' }
    $owners = @(Get-NetTCPConnection -State Listen -LocalPort 8000).OwningProcess
    if ($owners -notcontains $serverId) { throw 'Port ownership changed; retry.' }
    $jobs = Invoke-RestMethod 'http://127.0.0.1:8000/api/uploads?active_only=true' -TimeoutSec 3
    if ($null -ne $jobs -and $jobs.Count -gt 0) { throw 'An upload started; stop cancelled.' }
    Stop-Process -Id $serverId -ErrorAction Stop
    Wait-Process -Id $serverId -Timeout 10 -ErrorAction SilentlyContinue
    if (Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq 8000) {
        throw 'Port 8000 is still occupied. No other process was stopped.'
    }
    Write-Host 'Server stopped. Paper data and model caches were not removed.'
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
