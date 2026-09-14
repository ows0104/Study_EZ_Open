<#
    러너를 로그온 때 띄운다. `/admin`의 「Pre-Quiz 만들기」가 이것을 기다린다.

        StudyEZ Agent   로그온 5분 뒤 시작 · 죽으면 다시 띄운다 · 시간 제한 없음

    **이것은 예전 야간 작업과 다른 물건이다.** 04:00·06:00에 한 번씩 깨어나
    무언가를 하던 것이 아니라, 계속 떠서 사람이 누른 일감을 기다린다. 크론을
    걷어낸 이유는 `runner/agent.py` 첫머리에 있다 — 요약하면 닷새 동안 아무것도
    안 올리면서 종료 코드 0을 냈다.

    로그온 5분 뒤인 이유: 깨어난 직후에는 SynologyDrive가 아직 안 올라와 있다.
    야간 작업 넷이 전부 그 시각(따라잡기 회차)에 빈손으로 끝났고, 그중 하나는
    2초 사이에 폴더가 보였다 안 보였다 했다. 러너는 계속 떠 있으므로 5분을
    늦게 시작해도 잃는 것이 없다.

    관리자 권한은 필요 없다. 로그온한 사용자로 등록되고, **로그온해 있어야 돈다.**

    쓰는 법:
        powershell -ExecutionPolicy Bypass -File scripts\install-agent-task.ps1
        powershell -ExecutionPolicy Bypass -File scripts\install-agent-task.ps1 -Subject 병리학
        powershell -ExecutionPolicy Bypass -File scripts\install-agent-task.ps1 -Remove
#>
[CmdletBinding()]
param(
    [string]$TaskName = "StudyEZ Agent",
    # 쓸기를 이 과목으로 좁힌다. 안 주면 필기가 있는 과목 전부.
    # 일감 처리는 과목과 무관하다 — 서버가 어느 강의인지 같이 준다.
    [string]$Subject = "",
    [int]$DelayMinutes = 5,
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

if ($Remove) {
    $found = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($found) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "지웠다: $TaskName"
    }
    else { Write-Host "없다:   $TaskName" }
    exit 0
}

# **창을 숨긴다.** 안 숨기면 로그온할 때마다 검은 콘솔이 하나 떠서 종일 남는다.
# 종일 도는 물건이라 그 창은 사람이 닫고 싶어지고, 닫으면 러너가 죽는다.
# 볼 것은 runs\agent.log 에 있다.
$arguments = @("-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
               "-ExecutionPolicy", "Bypass",
               "-File", "`"$repo\scripts\agent.ps1`"")
if ($Subject) { $arguments += @("-Subject", $Subject) }

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument ($arguments -join " ") -WorkingDirectory $repo

# **로그온 트리거에 사용자를 박는다.** 안 박으면 "누가 로그온하든"이 되고, 그건
# 관리자 권한이 있어야 등록된다 (0x80070005). 우리는 이 계정에서만 돌면 된다.
$me = "$env:USERDOMAIN\$env:USERNAME"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $me
$trigger.Delay = "PT$($DelayMinutes)M"

# **시간 제한을 없앤다.** 예전 작업은 4시간에서 잘렸고, 실제로 그렇게 죽었다
# (0xC000013A). 러너는 종일 떠 있는 것이 정상이다.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -RestartInterval (New-TimeSpan -Minutes 5) -RestartCount 100

$principal = New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Study_EZ 러너 — /admin의 Pre-Quiz 일감을 집어 만들고 올린다" `
    -Force | Out-Null

Write-Host "걸었다: $TaskName (로그온 $($DelayMinutes)분 뒤 시작)"
Write-Host "  로그: $repo\runs\agent.log"
Write-Host "  창은 안 뜬다. 도는지 보려면: Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "  지금 바로 띄우려면: Start-ScheduledTask -TaskName '$TaskName'"
