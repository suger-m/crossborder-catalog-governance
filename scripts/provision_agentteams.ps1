param(
    [string]$AgentTeamsRoot = "$(if ($env:AGENTTEAMS_REPO) { $env:AGENTTEAMS_REPO } else { 'D:\\vibe\\AgentTeams' })",
    [string]$WorkspaceDir = "$(if ($env:AGENTTEAMS_WORKSPACE_DIR) { $env:AGENTTEAMS_WORKSPACE_DIR } else { "$env:USERPROFILE\\agentteams-manager" })",
    [string]$Model = "$(if ($env:AGENTTEAMS_DEFAULT_MODEL) { $env:AGENTTEAMS_DEFAULT_MODEL } elseif ($env:LLM_MODEL) { $env:LLM_MODEL } else { 'qwen3.6-plus' })"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$template = Join-Path $repoRoot "agentteams\\crossborder-workers.yaml"
if (-not (Test-Path -LiteralPath $template)) { throw "找不到 Worker 配置模板：$template" }
if (-not (Test-Path -LiteralPath $WorkspaceDir)) { New-Item -ItemType Directory -Path $WorkspaceDir -Force | Out-Null }

# AgentTeams Manager reads third-party Skills from this host-mounted directory.
$skillRoot = Join-Path $WorkspaceDir "worker-skills"
if (Test-Path -LiteralPath (Join-Path $repoRoot "skills")) {
    New-Item -ItemType Directory -Path $skillRoot -Force | Out-Null
    Copy-Item -Path (Join-Path $repoRoot "skills\\*") -Destination $skillRoot -Recurse -Force
}

$tmp = Join-Path $env:TEMP "crossborder-workers-$([guid]::NewGuid().ToString('N')).yaml"
try {
    (Get-Content -LiteralPath $template -Raw).Replace('__MODEL__', $Model) | Set-Content -LiteralPath $tmp -Encoding UTF8
    docker cp $tmp agentteams-manager:/tmp/crossborder-workers.yaml | Out-Null
    docker exec agentteams-manager agt apply -f /tmp/crossborder-workers.yaml
    Write-Host "已通过 AgentTeams 官方 agt 声明式接口提交四个跨境业务 Worker。"
    Write-Host "技能源目录：$skillRoot"

    # QwenPaw's declared MCP clients default to `ask`.  That default is
    # correct for an interactive user, but it would turn every deterministic
    # catalog/compliance call into an unresolved generic approval and stall a
    # Worker.  The business MCP bridge is already role-scoped and its own
    # platform services enforce domain approvals, so persist an explicit
    # allow policy through the official QwenPaw console API.  This does not
    # grant a Worker terminal/browser/search access.
    $mcpClients = @{
        "crossborder-catalog-steward" = "crossborder_catalog"
        "crossborder-compliance-specialist" = "crossborder_compliance"
        "crossborder-listing-operations" = "crossborder_listing"
        "crossborder-governance-reviewer" = "crossborder_governance"
    }
    $policyJson = '{"default_effect":"allow","client_overrides":[],"tool_defaults":[],"tool_overrides":[]}'
    foreach ($entry in $mcpClients.GetEnumerator()) {
        $container = "agentteams-worker-$($entry.Key)"
        $ready = $false
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            $probe = docker exec $container python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8088/api/version', timeout=2).read()" 2>$null
            if ($LASTEXITCODE -eq 0) { $ready = $true; break }
            Start-Sleep -Seconds 2
        }
        if (-not $ready) { throw "Worker QwenPaw API 未就绪：$container" }
        $encodedPolicy = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($policyJson))
        $clientKey = $entry.Value
        $policyCode = @"
import base64, json, urllib.request
body = base64.b64decode('$encodedPolicy')
request = urllib.request.Request('http://127.0.0.1:8088/api/mcp/policy/$clientKey', data=body, headers={'Content-Type':'application/json'}, method='PUT')
with urllib.request.urlopen(request, timeout=10) as response:
    payload = json.load(response)
assert payload.get('default_effect') == 'allow', payload
print(payload.get('default_effect'))
"@
        $policyEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($policyCode))
        $policyResult = docker exec $container python3 -c "import base64; exec(compile(base64.b64decode('$policyEncoded'), '<agentteams-policy>', 'exec'))"
        if ($LASTEXITCODE -ne 0) { throw "Worker MCP 策略配置失败：$container/$clientKey" }
        Write-Host "已配置 Worker MCP 策略：$container/$clientKey -> allow"
    }
}
finally {
    if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
}
