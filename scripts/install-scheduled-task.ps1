<#
    야간 작업 둘을 Windows 작업 스케줄러에 건다.

        04:00  StudyEZ Prequiz Build   예습 링크 → Pre-Quiz 문항까지 (모델이 돈다)
        06:00  StudyEZ Publish Sweep   아직 안 올라간 것을 쓸어담아 올린다

    **순서가 뜻이 있다.** 예습 빌드가 먼저 끝나야 그날 만든 덱을 쓸기가 받는다.
    빌드 쪽은 스킬 6단계가 스스로 올리므로 대개 쓸기까지 안 가지만, 중간에
    끊긴 편은 06:00이 받는다.

    `schtasks`를 직접 부르지 않고 ScheduledTasks 모듈을 쓰는 이유는 하나다 —
    **-StartWhenAvailable.** 노트북이 그 시각에 자고 있으면 schtasks로 건 작업은
    그날치를 통째로 거른다. 이 설정이 있으면 깨어난 뒤 밀린 회차를 한 번 돈다.

    관리자 권한은 필요 없다. 로그인한 사용자로 등록되고, 그래서 **로그온해
    있어야 돈다.**

    쓰는 법:
        powershell -ExecutionPolicy Bypass -File scripts\install-scheduled-task.ps1
        powershell -ExecutionPolicy Bypass -File scripts\install-scheduled-task.ps1 -At 07:30
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
    # 하룻밤에 몇 편까지 만들까. 편당 실측 약 34분 · Opus 호출 4회다.
    [int]$PrequizMax = 2,
    # 강의가 이 날짜 안에 있는 것만. 0이면 제한 없음.
    [int]$PrequizWithinDays = 0,

    [ValidateSet("both", "publish", "prequiz")]
    [string]$Only = "both",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$doPublish = $Only -in @("both", "publish")
$doPrequiz = $Only -in @("both", "prequiz")

if ($Remove) {
    foreach ($name in @($(if ($doPublish) { $TaskName }), $(if ($doPrequiz) { $PrequizTaskName }))) {
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

if ($doPrequiz) {
    $extra = "-Max $PrequizMax"
    if ($PrequizWithinDays -gt 0) { $extra += " -WithinDays $PrequizWithinDays" }

    # 한 편 75분 × 상한 + 넉넉히. 시간 제한에 걸려 중간에 끊기면 그 편의
    # 산출물이 반만 남는다.
    $hours = [math]::Max(4, [math]::Ceiling(($PrequizMax * 75) / 60.0) + 1)

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
if ($doPrequiz) { Write-Host "    Start-ScheduledTask -TaskName '$PrequizTaskName'" }
if ($doPublish) { Write-Host "    Start-ScheduledTask -TaskName '$TaskName'" }
