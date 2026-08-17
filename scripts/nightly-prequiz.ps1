<#
    예습 링크에서 Pre-Quiz까지, 사람 없이.

        1. studyez prequeue      작년 짝 고르기 · prep · preview.md  (코드)
        2. claude -p "/prequiz"  청사진 · 문항 · 감사 · 빌드          (모델)
        3. studyez done          덱·문항·링크를 올린다               (스킬 6단계가 부른다)

    2가 이 스크립트가 있는 이유다. 나머지는 이미 자동이었고 거기만 사람이
    세션을 열어야 했다.

    ## 무엇을 고르나

    `runs/prequeue.json`에서 `state`가 `ready`(아직 안 만듦)이거나
    `stale`(다른 대화로 만든 덱이 있음)인 것만. **강의 날짜가 이른 순서**로
    고른다 — 내일 강의가 다음 주 강의보다 급하다.

    `-Max`로 몇 편까지 돌릴지 막는다. 편당 실측 약 34분이고 Opus 호출이 네 번
    들어가므로 상한 없이 두면 밀린 링크가 스무 개일 때 밤새 돈다. **자른 것은
    로그에 적는다** — 조용히 자르면 다 만든 줄로 읽힌다.

    ## 성공 판정을 종료 코드로 하지 않는다

    `claude -p`는 모델이 "못 하겠다"고 답하고 끝나도 0으로 끝난다. 그래서
    `pre_items.final.json`이 **이 실행 뒤에 새로 쓰였는지**로 가른다. 그것이
    5단계 빌드가 실제로 지나갔다는 유일한 증거다.

    ## 권한

    `--allowedTools`로 이 실행에만 준다. 프로젝트 설정에 넣지 않는 이유는
    그러면 사람이 여는 세션까지 같이 넓어지기 때문이다. 무인으로 도는 34분짜리
    파이프라인이라 Bash를 통째로 열어야 하는데, 가둬 두는 것은 **프롬프트가
    고정(`/prequiz <경로>`)이고 저장소가 고정이고 전부 로그에 남는다**는 쪽이다.
    거부가 하나라도 나면 로그에 적는다.

    **이 스크립트는 서버에 올린다.** 스킬 6단계가 `studyez done`을 부르고, 그것이
    덱·문항·예습 링크를 밀어 넣는다. 올리기 전에 보고 싶으면 `-DryRun`.

    쓰는 법:
        powershell -File scripts\nightly-prequiz.ps1 -DryRun
        powershell -File scripts\nightly-prequiz.ps1
        powershell -File scripts\nightly-prequiz.ps1 -Max 5 -WithinDays 7
#>
[CmdletBinding()]
param(
    [string]$Python = "",
    [string]$Claude = "",
    [string]$Api = "",
    # 하룻밤에 몇 편까지. 편당 34분 · Opus 4회다.
    [int]$Max = 2,
    # 강의가 오늘부터 이 날짜 안에 있는 것만. 0이면 제한 없음.
    [int]$WithinDays = 0,
    [string]$Model = "opus",
    [string]$PermissionMode = "acceptEdits",
    # 한 편이 이만큼을 넘기면 끊고 다음 편으로 간다. 실측 34분의 두 배 남짓.
    [int]$TimeoutMinutes = 75,
    # 자리만 세우고 문항은 안 만든다 (= studyez prequeue 만).
    [switch]$NoBuild,
    [switch]$NoPrequeue,
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
    # -Width가 없으면 콘솔 폭에서 줄을 접는다. 무인 실행의 로그는 사람이
    # 나중에 읽는 유일한 자리라 한 줄이 두 줄로 갈리면 안 된다.
    $Lines | Out-File -FilePath $logPath -Append -Encoding utf8 -Width 4096
    $Lines | ForEach-Object { Write-Host $_ }
}

function Stamp { Get-Date -Format "yyyy-MM-dd HH:mm:ss" }

# ---------------------------------------------------------------- 실행 파일 찾기

# 이 저장소는 PATH의 python이 아니라 anaconda로 돈다 (SKILL.md와 같은 값).
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

# 작업 스케줄러에서는 PATH가 다를 수 있어 설치 자리를 직접 본다.
if (-not $Claude) {
    $candidate = Join-Path $env:USERPROFILE ".local\bin\claude.exe"
    if (Test-Path $candidate) { $Claude = $candidate }
}
if (-not $Claude) {
    $found = Get-Command claude -ErrorAction SilentlyContinue
    if ($found) { $Claude = $found.Source }
}

Write-Log @("", ("=" * 72), "[$(Stamp)] 예습 자동 빌드 시작", ("=" * 72))

# ---------------------------------------------------------------- 1. 자리 세우기

$env:PYTHONIOENCODING = "utf-8"

if (-not $NoPrequeue) {
    $arguments = @("-m", "studyez", "prequeue")
    if ($Api) { $arguments += @("--api", $Api) }

    Write-Log @("", "[1] $Python $($arguments -join ' ')")
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
    if ($exit -ne 0) {
        Write-Log @("[prequeue] 종료 코드 $exit — 큐를 못 세웠다. 여기서 멈춘다.")
        exit $exit
    }
}

# ---------------------------------------------------------------- 2. 무엇을 만들까

$queuePath = Join-Path $repo "runs\prequeue.json"
if (-not (Test-Path $queuePath)) {
    Write-Log @("", "[2] $queuePath 가 없다 — 만들 것이 없다.")
    exit 0
}

$queue = Get-Content $queuePath -Raw -Encoding UTF8 | ConvertFrom-Json
$items = @($queue.items | Where-Object { $_.state -eq "ready" -or $_.state -eq "stale" })
$items = @($items | Sort-Object { $_.link.date })

if ($WithinDays -gt 0) {
    $limit = (Get-Date).Date.AddDays($WithinDays)
    $far = @($items | Where-Object { [datetime]$_.link.date -gt $limit })
    foreach ($item in $far) {
        Write-Log @("  · 미룸 — $($item.link.run_id) $($item.link.title) " +
                    "($($item.link.date)) 는 $WithinDays 일 밖이다")
    }
    $items = @($items | Where-Object { [datetime]$_.link.date -le $limit })
}

if ($items.Count -eq 0) {
    Write-Log @("", "[2] 만들 것이 없다 — ready·stale 인 편이 없다.")
    exit 0
}

# 자른 것은 반드시 적는다. 조용히 자르면 다 만든 줄로 읽힌다.
if ($Max -lt 1) {
    Write-Log @("", "[2] -Max $Max — 한 편도 만들지 않는다.")
    exit 0
}
if ($items.Count -gt $Max) {
    foreach ($item in $items[$Max..($items.Count - 1)]) {
        Write-Log @("  · 오늘은 못 함 — $($item.link.run_id) $($item.link.title) " +
                    "($($item.link.date)) · 상한 $Max 편 초과. 다음 실행에서 다시 잡힌다")
    }
    $items = @($items[0..($Max - 1)])
}

Write-Log @("", "[2] 만들 편 $($items.Count)개 (상한 $Max)")
foreach ($item in $items) {
    Write-Log @("    $($item.link.date)  $($item.link.run_id) → 작년 $($item.prev_run_id)  " +
                "[$($item.state)]  $($item.link.title)")
}

if ($DryRun -or $NoBuild) {
    $why = if ($DryRun) { "--DryRun" } else { "--NoBuild" }
    Write-Log @("", "$why — 문항은 만들지 않았다. 자리는 위에 적힌 대로 서 있다.")
    exit 0
}

if (-not $Claude) {
    Write-Log @("", "claude CLI를 못 찾았다 — 문항을 만들지 못한다.",
                "  -Claude 로 경로를 주거나 PATH에 올려라. 자리는 이미 서 있으므로",
                "  세션에서 손으로 /prequiz 를 돌려도 된다.")
    exit 2
}

# ---------------------------------------------------------------- 3. 한 편씩 만든다

$built = 0
$failed = @()
$costTotal = 0.0

foreach ($item in $items) {
    $runDir = Join-Path $repo "runs\$($item.prev_run_id)"
    $finalPath = Join-Path $runDir "pre_items.final.json"
    # 성공 판정의 기준선. 종료 코드가 아니라 이 파일이 새로 쓰였는지로 가른다.
    $before = if (Test-Path $finalPath) { (Get-Item $finalPath).LastWriteTimeUtc } else { [datetime]::MinValue }

    $label = "$($item.link.run_id) $($item.link.title)"
    Write-Log @("", ("-" * 72), "[$(Stamp)] /prequiz $label → 작년 $($item.prev_run_id)")

    $prompt = "/prequiz `"$($item.prev_pdf)`""
    $cliArgs = @(
        "-p", $prompt,
        "--model", $Model,
        "--permission-mode", $PermissionMode,
        # **PowerShell이 빠지면 안 된다.** 이 환경의 기본 셸이 그쪽이라 첫 실측에서
        # 거부가 11건 났다. 세션은 Bash로 우회해 끝까지 갔지만 턴을 그만큼 버렸다.
        "--allowedTools", "Bash", "PowerShell", "Read", "Write", "Edit",
        "Glob", "Grep", "Task", "TodoWrite",
        "--output-format", "json"
    )

    $started = Get-Date
    # 별도 잡으로 띄운다 — 한 편이 멈춰 서도 나머지 편이 그것 때문에 밤을
    # 통째로 잃지 않게 시간을 재서 끊는다.
    $job = Start-Job -ScriptBlock {
        param($exe, $cwd, $jobArgs)
        Set-Location $cwd
        # 자식 프로세스의 출력을 UTF-8로 읽는다. 안 세우면 Windows 기본 cp949로
        # 디코드해서 **한글 보고가 통째로 깨진다** — 첫 실측 로그가 그랬다.
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $OutputEncoding = [System.Text.Encoding]::UTF8
        $ErrorActionPreference = "Continue"
        & $exe @jobArgs 2>&1 | ForEach-Object { $_.ToString() }
    } -ArgumentList $Claude, $repo, $cliArgs

    $finished = Wait-Job $job -Timeout ($TimeoutMinutes * 60)
    if ($null -eq $finished) {
        Stop-Job $job
        Remove-Job $job -Force
        $failed += "$label — $TimeoutMinutes 분을 넘겨 끊었다"
        Write-Log @("  ✗ $TimeoutMinutes 분 초과 — 끊고 다음 편으로 간다")
        continue
    }
    $raw = (Receive-Job $job) -join "`n"
    Remove-Job $job -Force
    $elapsed = ((Get-Date) - $started).TotalMinutes

    # `--output-format json`은 한 덩어리를 낸다. 못 읽으면 원문을 그대로 남긴다.
    $answer = $null
    try { $answer = $raw | ConvertFrom-Json } catch { $answer = $null }

    if ($answer) {
        $costTotal += [double]$answer.total_cost_usd
        Write-Log @("  세션 $($answer.session_id) · $([math]::Round($elapsed,1))분 · " +
                    "`$$([math]::Round($answer.total_cost_usd,2)) · 턴 $($answer.num_turns)")
        if ($answer.permission_denials -and $answer.permission_denials.Count -gt 0) {
            # 무인 실행에서 거부가 났다는 것은 이 스크립트의 --allowedTools가
            # 모자란다는 뜻이다. 다음 실행도 같은 자리에서 걸린다.
            Write-Log @("  ⚠ 권한 거부 $($answer.permission_denials.Count)건 — " +
                        "--allowedTools 가 모자란다: " +
                        (($answer.permission_denials | ForEach-Object { $_.tool_name }) -join ", "))
        }
        foreach ($line in ("$($answer.result)" -split "`n")) { Write-Log @("  | $line") }
    }
    else {
        Write-Log @("  세션 응답을 JSON으로 못 읽었다 · $([math]::Round($elapsed,1))분")
        foreach ($line in ($raw -split "`n" | Select-Object -Last 20)) { Write-Log @("  | $line") }
    }

    $after = if (Test-Path $finalPath) { (Get-Item $finalPath).LastWriteTimeUtc } else { [datetime]::MinValue }
    if ($after -gt $before) {
        $built++
        Write-Log @("  ✓ pre_items.final.json 이 새로 쓰였다 — 빌드가 지나갔다")
    }
    else {
        $failed += "$label — pre_items.final.json 이 안 나왔다"
        Write-Log @("  ✗ pre_items.final.json 이 안 나왔다 — 어디서 멈췄는지 위를 보라")
    }
}

# ---------------------------------------------------------------- 보고

Write-Log @("", ("=" * 72),
            "[$(Stamp)] 끝 — 만든 편 $built · 실패 $($failed.Count) · " +
            "합계 `$$([math]::Round($costTotal,2))")
foreach ($line in $failed) { Write-Log @("  ✗ $line") }
if ($built -gt 0) {
    Write-Log @("  올리는 것은 스킬 6단계의 `studyez done`이 이미 했다.",
                "  놓친 것이 있으면 06:00 쓸기가 받는다.")
}

exit $(if ($failed.Count -gt 0) { 1 } else { 0 })
