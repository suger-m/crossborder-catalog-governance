param(
    [string]$AgentTeamsRoot = "$(if ($env:AGENTTEAMS_REPO) { $env:AGENTTEAMS_REPO } else { 'D:\vibe\AgentTeams' })",
    [switch]$Install,
    [switch]$SkipProvision
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $AgentTeamsRoot)) {
    throw "AgentTeams 源码目录不存在：$AgentTeamsRoot"
}
docker info | Out-Null

$running = docker ps --filter "name=agentteams-manager" --format "{{.Names}}"
if ($running -notcontains "agentteams-manager" -or $Install) {
    if (-not $env:AGENTTEAMS_LLM_API_KEY) {
        $env:AGENTTEAMS_LLM_API_KEY = if ($env:COWORK_LLM_API_KEY) { $env:COWORK_LLM_API_KEY } else { $env:LLM_API_KEY }
    }
    if (-not $env:AGENTTEAMS_OPENAI_BASE_URL) {
        $env:AGENTTEAMS_OPENAI_BASE_URL = if ($env:COWORK_LLM_BASE_URL) { $env:COWORK_LLM_BASE_URL } else { $env:LLM_BASE_URL }
    }
    if (-not $env:AGENTTEAMS_DEFAULT_MODEL) {
        $env:AGENTTEAMS_DEFAULT_MODEL = if ($env:COWORK_LLM_MODEL) { $env:COWORK_LLM_MODEL } else { $env:LLM_MODEL }
    }
    if (-not $env:AGENTTEAMS_LLM_API_KEY) {
        throw "请先设置 AGENTTEAMS_LLM_API_KEY 或项目的 LLM_API_KEY。"
    }
    & pwsh -NoProfile -File (Join-Path $AgentTeamsRoot "install\agentteams-install.ps1") -NonInteractive
}

docker ps --filter "name=agentteams" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
if (-not $SkipProvision) {
    & (Join-Path $PSScriptRoot "provision_agentteams.ps1") -AgentTeamsRoot $AgentTeamsRoot
}

# The embedded Controller keeps its 8090 API and MinIO 9000 endpoint inside
# the AgentTeams container.  Publish those official endpoints through tiny
# read-only TCP forwarders so the host Web requester can use the same
# Controller/Object-Storage contracts without a local state adapter.
function Ensure-AgentTeamsProxy {
    param(
        [string]$Name,
        [int]$HostPort,
        [int]$ListenPort,
        [string]$TargetHost,
        [int]$TargetPort
    )
    $running = docker ps --filter "name=^$Name$" --format "{{.Names}}"
    if ($running -contains $Name) { return }
    $existing = docker ps -a --filter "name=^$Name$" --format "{{.Names}}"
    if ($existing -contains $Name) { docker rm -f $Name | Out-Null }
    $image = docker inspect agentteams-manager --format "{{.Config.Image}}"
    $proxy = @'
import socketserver, socket, select, sys
target = (sys.argv[1], int(sys.argv[2]))
class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        upstream = socket.create_connection(target)
        sockets = [self.request, upstream]
        try:
            while True:
                readable, _, _ = select.select(sockets, [], [])
                for current in readable:
                    data = current.recv(65536)
                    if not data:
                        return
                    (upstream if current is self.request else self.request).sendall(data)
        finally:
            upstream.close()
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
Server(("0.0.0.0", int(sys.argv[3])), Handler).serve_forever()
'@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($proxy))
    $runner = "import base64;exec(compile(base64.b64decode('$encoded'),'<agentteams-proxy>','exec'))"
    docker run -d --restart unless-stopped --name $Name --network agentteams-net `
        -p "127.0.0.1:${HostPort}:${ListenPort}" --entrypoint python3 $image `
        -c $runner $TargetHost $TargetPort $ListenPort | Out-Null
}

Ensure-AgentTeamsProxy -Name "agentteams-controller-api-proxy" -HostPort 18090 -ListenPort 8090 -TargetHost "agentteams-controller" -TargetPort 8090
Ensure-AgentTeamsProxy -Name "agentteams-storage-proxy" -HostPort 19000 -ListenPort 9000 -TargetHost "agentteams-controller" -TargetPort 9000

# Pass the official runtime credentials to the Web process through the current
# PowerShell session.  They are read from the running Controller and never
# committed to the repository or written to a project settings file.
$env:AGENTTEAMS_CONTROLLER_PUBLIC_URL = "http://127.0.0.1:18090"
$env:AGENTTEAMS_FS_PUBLIC_URL = "http://127.0.0.1:19000"
$env:AGENTTEAMS_FS_BUCKET = "agentteams-storage"
$env:AGENTTEAMS_FS_ACCESS_KEY = "default"
$env:AGENTTEAMS_FS_SECRET_KEY = (docker inspect agentteams-manager --format "{{range .Config.Env}}{{println .}}{{end}}" | Select-String '^AGENTTEAMS_FS_SECRET_KEY=').Line.Split('=', 2)[1]
$env:AGENTTEAMS_AUTH_TOKEN = (docker exec agentteams-controller sh -lc 'cat /var/run/agentteams/cli-token').Trim()

Write-Host "AgentTeams Controller API: $env:AGENTTEAMS_CONTROLLER_PUBLIC_URL"
Write-Host "AgentTeams shared storage: $env:AGENTTEAMS_FS_PUBLIC_URL"
Write-Host "现在启动跨境 Web 后端：python -m crossborder_cowork.app"
