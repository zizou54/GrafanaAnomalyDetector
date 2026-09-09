param([switch]$LocalLab)
$ErrorActionPreference = 'Stop'
if (-not $LocalLab) { throw 'Explicit -LocalLab required. Never run against production.' }
function Health {
    $response = Invoke-WebRequest 'http://127.0.0.1:9110/health/dependencies' -SkipHttpErrorCheck -TimeoutSec 20
    return ($response.Content | ConvertFrom-Json)
}
$results = @()
foreach ($entry in @(
    @{sink='postgresql'; container='anomaly_multi_postgres'},
    @{sink='loki'; container='anomaly_multi_loki'},
    @{sink='influxdb'; container='anomaly_multi_influxdb'},
    @{sink='clickhouse'; container='anomaly_multi_clickhouse'},
    @{sink='elasticsearch'; container='anomaly_multi_elasticsearch'}
)) {
    $before = (Health).sinks | Where-Object name -eq $entry.sink
    $observedFailure = $false
    try {
        docker stop --time 2 $entry.container | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not stop test sink' }
        $deadline = (Get-Date).AddSeconds(40)
        do {
            Start-Sleep -Seconds 3
            $status = (Health).sinks | Where-Object name -eq $entry.sink
            $observedFailure = -not $status.up
        } until ($observedFailure -or (Get-Date) -ge $deadline)
    } finally {
        docker start $entry.container | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Restore required: $($entry.container)" }
    }
    $started = Get-Date
    $recovered = $false
    do {
        Start-Sleep -Seconds 3
        $status = (Health).sinks | Where-Object name -eq $entry.sink
        $recovered = $status.up -and $status.lastWriteTimestampSeconds -gt $before.lastWriteTimestampSeconds
    } until ($recovered -or ((Get-Date) - $started).TotalSeconds -gt 150)
    $row = @{sink=$entry.sink; failureObserved=$observedFailure; recovered=$recovered;
        recoverySeconds=[math]::Round(((Get-Date)-$started).TotalSeconds, 1);
        passed=($observedFailure -and $recovered)}
    $results += $row
    $row | ConvertTo-Json -Compress
}
$healthy = (Health).dependenciesHealthy
@{passed=($healthy -and @($results | Where-Object {-not $_.passed}).Count -eq 0);
  finalDependenciesHealthy=$healthy; sinks=$results.Count} | ConvertTo-Json -Compress
if (-not $healthy -or @($results | Where-Object {-not $_.passed}).Count) { exit 1 }
