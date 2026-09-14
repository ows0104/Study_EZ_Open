<#
    ※ 2026-08-23부터 이 작업은 스케줄러에 등록되어 있지 않다.
      만드는 것은 `/admin`의 「Pre-Quiz 만들기」와 `python -m runner agent`가 한다
      (README §만드는 것은 버튼이 시작한다). 배선을 남겨 두는 것은 되돌릴 자리가
      필요할 때를 위해서다 — `install-scheduled-task.ps1`로 다시 걸 수 있다.
#>
<#
    야간 작업을 Windows 작업 스케줄러에 건다.

        21:30  StudyEZ Quiz Build      새 필기 → 복습 덱      (-WithQuiz 를 줘야 걸린다)
        04:00  StudyEZ Prequiz Build   예습 링크 → 예습 덱
        06:00  StudyEZ Publish Sweep   만든 것을 쓸어담아 올린다

    **순서가 뜻이 있다.** 만드는 것이 먼저 끝나야 그날치를 쓸기가 받는다.
    중간에 끊긴 편은 다음 회차가 다시 잡는다.

    **복습 빌드는 기본으로 안 걸린다.** 편당 Opus 호출이 여러 번이고 그 비용이
    사람이 안 보는 동안 나간다. 손으로 몇 편 돌려 편당 비용
    (`runs\<run_id>\run.report.json` 의 `cumulative.cost_usd`)을 보고 나서
    `-WithQuiz` 로 건다.

    `schtasks`를 직접 부르지 않고 ScheduledTasks 모듈을 쓰는 이유는 하나다 —
    **-StartWhenAvailable.** 노트북이 그 시각에 자고 있으면 schtasks로 건 작업은
    그날치를 통째로 거른다. 이 설정이 있으면 깨어난 뒤 밀린 회차를 한 번 돈다.

    관리자 권한은 필요 없다. 로그인한 사용자로 등록되고, 그래서 **로그온해
    있어야 돈다.**

    쓰는 법:
        powershell -ExecutionPolicy Bypass -File scripts\install-scheduled-task.ps1
        powershell -ExecutionPolicy Bypass -File scripts\install-scheduled-task.ps1 -At 07:30
        powershell -ExecutionPolicy Bypass -File scripts\install-scheduled-task.ps1 -WithQuiz
        powershell -ExecutionPolicy Bypass -File scripts\install-scheduled-task.ps1 -Only publish
        powershell -ExecutionPolicy Bypass -File scripts\install-scheduled-task.ps1 -Remove
#>
[CmdletBinding()]
param(
    [string]$TaskName = "StudyEZ Publish Sweep",
    [string]$At = "06:00",
    # 과목을 주면 야간에 그 과목만 훑는다. 안 주면 필기가 있는 과목 전부.
    [string[]]$Subject = @(),

    [string]$PrequizTaskName = "StudyEZ Prequiz Build",
    [string]$PrequizAt = "04:00",
    # 하룻밤에 몇 편까지 만들까.
    [int]$PrequizMax = 2,
    # 강의가 이 날짜 안에 있는 것만. 0이면 제한 없음.
    [int]$PrequizWithinDays = 0,

    # 복습 덱까지 무인으로 만든다. 기본은 꺼져 있다 — 위 머리말을 보라.
    [switch]$WithQuiz,
    [string]$QuizTaskName = "StudyEZ Quiz Build",
    [string]$QuizAt = "21:30",
    [int]$QuizMax = 2,

    [ValidateSet("both", "all", "publish", "prequiz", "quiz")]
    [string]$Only = "both",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$doPublish = $Only -in @("both", "all", "publish")
$doPrequiz = $Only -in @("both", "all", "prequiz")
# `both`는 예전부터 「예습 + 쓸기」였다. 복습은 그 뜻을 바꾸지 않고 따로 켠다.
$doQuiz = ($Only -eq "quiz") -or ($WithQuiz -and $Only -in @("both", "all"))

if ($Remove) {
    foreach ($name in @($(if ($doPublish) { $TaskName }), $(if ($doPrequiz) { $PrequizTaskName }),
                        $(if ($doQuiz -or $Only -in @("both", "all")) { $QuizTaskName }))) {
        if (-not $name) { continue }
        $found = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($found) {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
            Write-Host "지웠다: $name"
        }
        else {
            Write-Host "없다:   $name"
        }
    }
    exit 0
}

# 배터리로도 돌린다. 이미 도는 회차가 있으면 새 회차는 버린다 — 두 벌이 같은
# 산출물 디렉터리에 겹쳐 쓰면 무엇이 참인지 알 수 없게 된다.
function New-Settings([int]$Hours) {
    New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours $Hours) `
        -MultipleInstances IgnoreNew
}

function Register-One([string]$Name, [string]$Script, [string]$Extra,
                      [string]$When, [int]$Hours, [string]$Description) {
    if (-not (Test-Path $Script)) {
        Write-Host "없다: $Script"
        exit 2
    }
    $argument = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Script`""
    if ($Extra) { $argument += " $Extra" }

    Register-ScheduledTask `
        -TaskName $Name `
        -Action (New-ScheduledTaskAction -Execute "powershell.exe" `
                    -Argument $argument -WorkingDirectory $repo) `
        -Trigger (New-ScheduledTaskTrigger -Daily -At $When) `
        -Settings (New-Settings $Hours) `
        -Description $Description `
        -Force | Out-Null
}

if ($doQuiz) {
    $extra = "-Max $QuizMax"
    if ($Subject.Count -gt 0) { $extra += " -Subject '$($Subject[0])'" }

    # 한 편 180분 × 상한 + 넉넉히. 시간 제한에 걸려 중간에 끊기면 그 편의
    # 산출물이 반만 남는다.
    $hours = [math]::Max(4, [math]::Ceiling(($QuizMax * 180) / 60.0) + 1)

    Register-One $QuizTaskName (Join-Path $PSScriptRoot "nightly-quiz.ps1") `
        $extra $QuizAt $hours `
        "Study_EZ — 새로 올라온 필기로 복습 덱을 만든다. 로그: runs\quiz.log"

    Write-Host "걸었다: $QuizTaskName — 매일 $QuizAt · 하룻밤 최대 $QuizMax 편 · 제한 $hours 시간"
    Write-Host "  로그: $(Join-Path $repo 'runs\quiz.log')"
}

if ($doPrequiz) {
    $extra = "-Max $PrequizMax"
    if ($PrequizWithinDays -gt 0) { $extra += " -WithinDays $PrequizWithinDays" }

    # 한 편 120분 × 상한 + 넉넉히. 시간 제한에 걸려 중간에 끊기면 그 편의
    # 산출물이 반만 남는다.
    $hours = [math]::Max(4, [math]::Ceiling(($PrequizMax * 120) / 60.0) + 1)

    Register-One $PrequizTaskName (Join-Path $PSScriptRoot "nightly-prequiz.ps1") `
        $extra $PrequizAt $hours `
        "Study_EZ — 관리자가 저장한 예습 링크로 Pre-Quiz를 만든다. 로그: runs\prequiz.log"

    Write-Host "걸었다: $PrequizTaskName — 매일 $PrequizAt · 하룻밤 최대 $PrequizMax 편 · 제한 $hours 시간"
    Write-Host "  로그: $(Join-Path $repo 'runs\prequiz.log')"
}

if ($doPublish) {
    $extra = ""
    if ($Subject.Count -gt 0) {
        $extra = "-Subject " + (($Subject | ForEach-Object { "'$_'" }) -join ",")
    }

    # 강의록이 편당 5~56MB라 두 시간이면 넉넉하다.
    Register-One $TaskName (Join-Path $PSScriptRoot "nightly-publish.ps1") `
        $extra $At 2 `
        "Study_EZ — 아직 안 올라간 강의록·덱을 하루 한 번 쓸어담아 올린다. 로그: runs\publish.log"

    $scope = if ($Subject.Count -gt 0) { $Subject -join ", " } else { "필기가 있는 과목 전부" }
    Write-Host "걸었다: $TaskName — 매일 $At · 대상: $scope"
    Write-Host "  로그: $(Join-Path $repo 'runs\publish.log')"
}

Write-Host ""
Write-Host "  지금 한 번 돌려 보려면:"
if ($doQuiz) { Write-Host "    Start-ScheduledTask -TaskName '$QuizTaskName'" }
if ($doPrequiz) { Write-Host "    Start-ScheduledTask -TaskName '$PrequizTaskName'" }
if ($doPublish) { Write-Host "    Start-ScheduledTask -TaskName '$TaskName'" }
