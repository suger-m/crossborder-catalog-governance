param(
    [string]$AppUrl = "http://127.0.0.1:8000",
    [string]$MatrixUrl = "$(if ($env:AGENTTEAMS_MATRIX_URL) { $env:AGENTTEAMS_MATRIX_URL } else { 'http://127.0.0.1:18080' })",
    [string]$ControllerUrl = "$(if ($env:AGENTTEAMS_CONTROLLER_PUBLIC_URL) { $env:AGENTTEAMS_CONTROLLER_PUBLIC_URL } else { 'http://127.0.0.1:18090' })",
    [string]$StorageUrl = "$(if ($env:AGENTTEAMS_FS_PUBLIC_URL) { $env:AGENTTEAMS_FS_PUBLIC_URL } else { 'http://127.0.0.1:19000' })"
)

$ErrorActionPreference = "Stop"
$app = Invoke-RestMethod "$AppUrl/health"
$agentteams = Invoke-RestMethod "$AppUrl/api/agentteams/health"
$matrix = Invoke-RestMethod "$MatrixUrl/_matrix/client/versions"
$controllerToken = $env:AGENTTEAMS_AUTH_TOKEN
if (-not $controllerToken) {
    $controllerToken = (docker exec agentteams-controller sh -lc 'cat /var/run/agentteams/cli-token').Trim()
}
if (-not $controllerToken) { throw "无法读取 AgentTeams Controller token。请先运行 scripts/start_agentteams.ps1。" }
$controllerStatus = (Invoke-WebRequest "$ControllerUrl/api/v1/workers" -Headers @{ Authorization = "Bearer $controllerToken" }).StatusCode
$storageStatus = (Invoke-WebRequest "$StorageUrl/minio/health/live").StatusCode
$workerCount = @($agentteams.runtime.workers).Count
[pscustomobject]@{
    app = $app.status
    agentteams = $agentteams.service_state.status
    matrix_versions = @($matrix.versions).Count
    controller_workers = $workerCount
    controller_http = $controllerStatus
    storage_http = $storageStatus
    ready = [bool]$agentteams.service_state.ready
} | ConvertTo-Json -Compress
if (-not $agentteams.service_state.ready) {
    throw "AgentTeams 尚未就绪：$($agentteams.service_state.last_error)"
}
