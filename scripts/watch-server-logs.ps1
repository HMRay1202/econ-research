[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ProjectDir,
    [string]$EncodingName = 'default',
    [switch]$Once
)

# Read-only observer: never starts/stops a server or writes to its log files.
# The redirected Windows Python logs use the system ANSI encoding by default.
$logEncoding = if ($EncodingName -eq 'default') {
    [System.Text.Encoding]::Default
} else {
    [System.Text.Encoding]::GetEncoding($EncodingName)
}
$states = @(
    @{ Path = (Join-Path $ProjectDir 'data/server-windows.stdout.log'); Offset = -1L },
    @{ Path = (Join-Path $ProjectDir 'data/server-windows.stderr.log'); Offset = -1L }
)
$share = [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
Write-Host 'READ-ONLY LOG VIEWER - Ctrl+C closes this viewer only; the server keeps running.'
Write-Host 'To stop a hidden server, run stop-research.cmd and confirm STOP (finish work first).'
Write-Host 'Watching redirected stdout and stderr. Sections are not globally time-sorted.'
Write-Host 'These files may contain older runs; check timestamps. A foreground server may log'
Write-Host 'only in its original terminal. Missing files will be watched until they appear.'

do {
    foreach ($state in $states) {
        $stream = $null
        try {
            # Share writes and deletion so the observer cannot prevent logging/rotation.
            $stream = [System.IO.FileStream]::new(
                $state.Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, $share
            )
            $length = $stream.Length
            $initial = $state.Offset -lt 0
            if ($initial) {
                $state.Offset = [Math]::Max(0L, $length - 65536L)
            } elseif ($length -lt $state.Offset) {
                $state.Offset = 0L
            }
            $count = [int][Math]::Min(65536L, $length - $state.Offset)
            if ($count -gt 0) {
                [void]$stream.Seek($state.Offset, [System.IO.SeekOrigin]::Begin)
                $buffer = New-Object byte[] $count
                $read = $stream.Read($buffer, 0, $count)
                $text = $logEncoding.GetString($buffer, 0, $read)
                $state.Offset += $read
                if ($initial) {
                    # Bound the initial display while retaining every subsequent update.
                    $text = (($text -split "`n" | Select-Object -Last 40) -join "`n")
                }
                Write-Host "`n--- $([System.IO.Path]::GetFileName($state.Path)) ---"
                Write-Host $text -NoNewline
            }
        } catch [System.IO.FileNotFoundException] {
            if ($state.Offset -ne -2L) { Write-Host "Waiting for log file: $($state.Path)" }
            $state.Offset = -2L
        } catch [System.IO.DirectoryNotFoundException] {
            if ($state.Offset -ne -2L) { Write-Host "Waiting for log directory: $($state.Path)" }
            $state.Offset = -2L
        } catch {
            Write-Warning "Cannot read $($state.Path): $($_.Exception.Message)"
        } finally {
            if ($null -ne $stream) { $stream.Dispose() }
        }
    }
    if (-not $Once) { Start-Sleep -Milliseconds 750 }
} while (-not $Once)
