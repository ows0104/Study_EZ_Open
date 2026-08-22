<#
    예습 링크에서 Pre-Quiz 덱까지, 사람 없이.

        python -m studyez prequeue --build

    **한 줄이다.** 예전에는 이 자리가 260줄이었다 — `claude -p "/prequiz <경로>"`로
    세션을 대신 띄우고, 권한 목록을 손으로 주고, 잡으로 감싸 시간을 재서 끊고,
    종료 코드를 못 믿어 `pre_items.final.json`의 수정 시각으로 성공을 가려야 했다.

    그 전부가 이제 파이프라인 안에 있다. `pdf2anki`가 모델이 필요한 자리마다 빈
    세션을 스스로 띄우고(`pdf2anki/session.py`), 상한·순서·시간 제한·성공 판정은
    `studyez.prequeue`가 든다. 여기 남은 것은 로그와 스케줄러 배선뿐이다.

    ## 무엇을 고르나

    `state`가 `ready`(아직 안 만듦)이거나 `stale`(다른 대화로 만든 덱이 있다)인 것.
    **강의 날짜가 이른 순서**로 — 내일 강의가 다음 주 강의보다 급하다.
    `-Max`가 하룻밤 상한, `-WithinDays`가 "이 날짜 안의 강의만"이다.
    **미룬 편은 로그에 이름이 적힌다** — 조용히 자르면 다 만든 줄로 읽힌다.

    올리는 것은 `studyez publish`이고 06:00 쓸기가 받는다.

    쓰는 법:
        powershell -File scripts\nightly-prequiz.ps1 -DryRun
        powershell -File scripts\nightly-prequiz.ps1
        powershell -File scripts\nightly-prequiz.ps1 -Max 5 -WithinDays 7
#>
[CmdletBinding()]
param(
    [string]$Python = "",
    [string]$Api = "",
    # 하룻밤에 몇 편까지. 편당 비용은 runs\<run_id>\run.report.json 에 남는다.
    [int]$Max = 2,
    # 강의가 오늘부터 이 날짜 안에 있는 것만. 0이면 제한 없음.
    [int]$WithinDays = 0,
    [string]$Model = "",
    # 한 편이 이만큼을 넘기면 그 편을 버리고 다음으로 간다.
    [int]$TimeoutMinutes = 120,
    # 자리만 세우고 덱은 안 만든다.
    [switch]$NoBuild,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$logPath = Join-Path $repo "runs\prequiz.log"

$logDir = Split-Path -Parent $logPath
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}
if (Test-Path $logPath) {
    if ((Get-Item $logPath).Length -gt 5MB) {
        Move-Item -Path $logPath -Destination "$logPath.1" -Force
    }
}

function Write-Log([string[]]$Lines) {
    # -Width가 없으면 콘솔 폭에서 줄을 접는다. 무인 실행의 로그는 사람이 나중에
    # 읽는 유일한 자리라 한 줄이 두 줄로 갈리면 안 된다.
    $Lines | Out-File -FilePath $logPath -Append -Encoding utf8 -Width 4096
    $Lines | ForEach-Object { Write-Host $_ }
}

function Stamp { Get-Date -Format "yyyy-MM-dd HH:mm:ss" }

# 이 저장소는 PATH의 python이 아니라 anaconda로 돈다.
if (-not $Python) {
    foreach ($candidate in @(
            (Join-Path $env:USERPROFILE "anaconda3\python.exe"),
            (Join-Path $env:USERPROFILE "miniconda3\python.exe"))) {
        if (Test-Path $candidate) { $Python = $candidate; break }
    }
}
if (-not $Python) {
    $found = Get-Command python -ErrorAction SilentlyContinue
    if ($found) { $Python = $found.Source }
}
if (-not $Python) {
    Write-Log @("", ("=" * 72), "[$(Stamp)] 파이썬을 못 찾았다 — 아무것도 하지 않았다.")
    exit 2
}

$arguments = @("-m", "studyez", "prequeue", "--max", "$Max",
               "--timeout", "$($TimeoutMinutes * 60)")
if (-not ($DryRun -or $NoBuild)) { $arguments += "--build" }
if ($DryRun) { $arguments += "--dry-run" }
if ($WithinDays -gt 0) { $arguments += @("--within-days", "$WithinDays") }
if ($Model) { $arguments += @("--model", $Model) }
if ($Api) { $arguments += @("--api", $Api) }

Write-Log @("", ("=" * 72), "[$(Stamp)] 예습 자동 빌드", "$Python $($arguments -join ' ')", ("=" * 72))

$env:PYTHONIOENCODING = "utf-8"
Push-Location $repo
try {
    # 병합한 ErrorRecord가 Stop에 걸려 스크립트를 죽이지 않도록 이 구간만 Continue.
    $prior = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & $Python @arguments 2>&1 | ForEach-Object { $_.ToString() }
    $exit = $LASTEXITCODE
    $ErrorActionPreference = $prior
}
finally {
    Pop-Location
}

Write-Log $output
Write-Log @("[$(Stamp)] 끝 — 종료 코드 $exit")
if ($exit -eq 0 -and -not ($DryRun -or $NoBuild)) {
    Write-Log @("  올리는 것은 06:00 쓸기가 받는다 (scripts\nightly-publish.ps1).")
}
exit $exit
