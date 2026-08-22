<#
    새로 올라온 올해 필기에서 복습 덱까지, 사람 없이.

        python -m studyez watch --build

    필기가 올라오는 것에서 시작한다(예습은 반대다 — 사람이 예습하는 것에서 시작한다).
    스캔·최신 판 고르기·블럭 좁히기는 `studyez.watch`가, prep부터 빌드까지는
    `pdf2anki`가 빈 세션을 스스로 띄워 한다.

    ## 이 작업은 기본으로 걸리지 않는다

    `install-scheduled-task.ps1`은 `-WithQuiz`를 줘야 이걸 등록한다. 편당 Opus
    호출이 여러 번이고 그 비용이 사람이 안 보는 동안 나가기 때문이다. **얼마나
    드는지 먼저 손으로 몇 편 돌려 보고 걸어라** — 편당 실제 비용은
    `runs\<run_id>\run.report.json`의 `cumulative.cost_usd`에 남는다.

    상한은 `-Max`(기본 2)다. 넘친 편은 다음 날 다시 잡힌다 — 표시가 `source.json`
    기준이라 만든 편만 빠진다.

    올리는 것은 06:00 쓸기가 받는다. 검문(`studyez.gate`)에 걸린 편은 강의록만
    나가고 덱은 미뤄진다.

    쓰는 법:
        powershell -File scripts\nightly-quiz.ps1 -DryRun
        powershell -File scripts\nightly-quiz.ps1
        powershell -File scripts\nightly-quiz.ps1 -Subject 병리학 -Max 3
#>
[CmdletBinding()]
param(
    [string]$Python = "",
    # 과목을 주면 그 과목만. 안 주면 필기가 있는 과목 전부.
    [string]$Subject = "",
    [int]$Max = 2,
    [string]$Model = "",
    # 한 편이 이만큼을 넘기면 그 편을 버리고 다음으로 간다.
    [int]$TimeoutMinutes = 180,
    # 블럭으로 안 좁힌다. 밀린 것을 몰아 만들 때만.
    [switch]$AllDates,
    # 스캔만 하고 덱은 안 만든다.
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$logPath = Join-Path $repo "runs\quiz.log"

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

$arguments = @("-m", "studyez", "watch", "--max", "$Max",
               "--timeout", "$($TimeoutMinutes * 60)")
if ($Subject) { $arguments += $Subject }
if (-not $DryRun) { $arguments += "--build" }
if ($AllDates) { $arguments += "--all-dates" }
if ($Model) { $arguments += @("--model", $Model) }

Write-Log @("", ("=" * 72), "[$(Stamp)] 복습 자동 빌드", "$Python $($arguments -join ' ')", ("=" * 72))

$env:PYTHONIOENCODING = "utf-8"
Push-Location $repo
try {
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
# 2는 "블럭을 못 정해 큐를 안 세웠다"이다. 실패가 아니라 **일부러 멈춘 것**이라
# 스케줄러가 붉게 칠하지 않도록 0으로 돌려준다. 이유는 로그에 이미 적혀 있다.
if ($exit -eq 2) {
    Write-Log @("  블럭을 못 정해 큐를 세우지 않았다 — 위를 보라. 실패로 세지 않는다.")
    exit 0
}
exit $exit
