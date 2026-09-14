<#
    러너를 띄운다. `python -m runner agent`에 파이썬 찾기와 로그만 붙인 것이다.

    **출력을 흘려 쓴다.** 예전 야간 스크립트는 자식이 끝난 뒤에야 로그를 썼고,
    그래서 2026-08-23 새벽에 강제 종료된 회차는 로그에 머리글만 남겼다. 러너는
    종일 떠 있으므로 그 방식이면 아무것도 안 보인다.

    쓰는 법:
        powershell -ExecutionPolicy Bypass -File scripts\agent.ps1
        powershell -ExecutionPolicy Bypass -File scripts\agent.ps1 -Subject 병리학
#>
[CmdletBinding()]
param(
    [string]$Python = "",
    [string]$Subject = "",
    [string]$Api = ""
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$logPath = Join-Path $repo "runs\agent.log"

$logDir = Split-Path -Parent $logPath
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

# 종일 도는 로그다. 5MB에서 한 세대만 접는다.
if ((Test-Path $logPath) -and (Get-Item $logPath).Length -gt 5MB) {
    Move-Item -Path $logPath -Destination "$logPath.1" -Force
}

# 이 저장소는 PATH의 python이 아니라 anaconda로 돈다.
if (-not $Python) {
    foreach ($candidate in @((Join-Path $env:USERPROFILE "anaconda3\python.exe"),
                             (Join-Path $env:USERPROFILE "miniconda3\python.exe"))) {
        if (Test-Path $candidate) { $Python = $candidate; break }
    }
}
if (-not $Python) {
    $found = Get-Command python -ErrorAction SilentlyContinue
    if ($found) { $Python = $found.Source }
}

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
if (-not $Python) {
    "[$stamp] 파이썬을 못 찾았다 — 러너를 띄우지 못했다." | Out-File $logPath -Append -Encoding utf8
    exit 2
}

$arguments = @("-m", "runner", "agent")
if ($Subject) { $arguments += $Subject }
if ($Api) { $arguments += @("--api", $Api) }

@("", ("=" * 72), "[$stamp] $Python $($arguments -join ' ')", ("=" * 72)) |
    Out-File $logPath -Append -Encoding utf8

$env:PYTHONIOENCODING = "utf-8"
# **자식의 UTF-8을 UTF-8로 읽는다.** 이걸 안 걸면 PowerShell이 ANSI 코드페이지로
# 디코딩해서 로그가 통째로 깨진다 — `runs/prequiz.log`가 몇 달째 그 꼴이었다.
$priorOut = [Console]::OutputEncoding
[Console]::OutputEncoding = [Text.Encoding]::UTF8
# **버퍼를 끈다**(-u). 안 그러면 종일 도는 프로세스의 로그가 블록 단위로 늦게 나와,
# 지금 무엇을 하는지 보려고 로그를 열었을 때 비어 있다.
Push-Location $repo
try {
    $prior = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    # `Tee-Object`는 5.1에서 UTF-16으로 쓴다 — 한글 로그가 깨진 채로 남는다.
    # 줄마다 UTF-8로 붙이고 화면에도 그대로 흘린다.
    & $Python -u @arguments 2>&1 | ForEach-Object {
        $line = $_.ToString()
        $line | Out-File -FilePath $logPath -Append -Encoding utf8
        Write-Host $line
    }
    $exit = $LASTEXITCODE
    $ErrorActionPreference = $prior
}
finally {
    Pop-Location
    [Console]::OutputEncoding = $priorOut
}

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 러너가 멈췄다 — 종료 코드 $exit" |
    Out-File $logPath -Append -Encoding utf8
exit $exit
