param(
    [string]$ResourcesDir = "",
    [string]$RuntimeDir = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $ResourcesDir) {
    $ResourcesDir = Join-Path $root "desktop\release\win-unpacked\resources"
}
if (-not $RuntimeDir) {
    $RuntimeDir = Join-Path $root "build\packaged-smoke-runtime"
}
$resources = (Resolve-Path $ResourcesDir).Path
$backend = Join-Path $resources "prebuilt\crossborder-backend.exe"
if (-not (Test-Path -LiteralPath $backend -PathType Leaf)) {
    throw "Packaged backend was not found: $backend"
}
New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
$environment = @{
    CROSSBORDER_COWORK_BASE_DIR = $resources
    CROSSBORDER_COWORK_RUNTIME_DIR = $RuntimeDir
}
foreach ($key in $environment.Keys) {
    [Environment]::SetEnvironmentVariable($key, $environment[$key], "Process")
}
$process = Start-Process -FilePath $backend -WorkingDirectory (Split-Path $backend) -PassThru -WindowStyle Hidden
try {
    $healthy = $false
    for ($attempt = 0; $attempt -lt 80; $attempt += 1) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 1
            if ($health.status -eq "ok") {
                $healthy = $true
                break
            }
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $healthy) {
        throw "Packaged backend did not become healthy within 20 seconds"
    }
    $taxonomies = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/taxonomies" -TimeoutSec 5
    $skills = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/skills" -TimeoutSec 5
    $models = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/model-settings/readiness" -TimeoutSec 5
    if ($taxonomies.items.Count -ne 4) {
        throw "Expected 4 packaged taxonomies, found $($taxonomies.items.Count)"
    }
    if ($skills.items.Count -ne 9) {
        throw "Expected 9 packaged skills, found $($skills.items.Count)"
    }
    $configuredRoles = @("planner", "worker", "reviewer") | Where-Object { $models.$_.configured }
    [pscustomobject]@{
        health = $health.status
        taxonomies = $taxonomies.items.Count
        skills = $skills.items.Count
        configured_model_roles = $configuredRoles.Count
        configured_roles = $configuredRoles
    } | ConvertTo-Json -Compress
}
finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}
