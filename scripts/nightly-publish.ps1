<#
    야간 쓸어담기 — 하루 한 번, 아직 안 올라간 것이 남았는지 훑고 민다.

    편이 끝날 때마다 `studyez done`이 그 편을 바로 올린다. 여기는 그것이
    놓친 자리를 받는다.

        야간 빌드가 만들었지만 아무도 안 올린 편
        업로드 중간에 끊긴 파일 (서버가 HEAD해서 missing으로 돌려준다)
        Pre-Quiz를 진도보다 앞서 만들어 둔 편 — 올해 필기가 그 사이 올라왔다
        필기가 새 판(v3)으로 갈려 강의록만 다시 밀어야 하는 편
        `studyez release`로 보류가 풀린 편

    `publish`는 멱등이라 겹쳐 돌아도 다시 안 민다. `runs/published.json`의
    표시와 서버의 HEAD 두 가지를 보고, 바뀐 것과 실제로 없는 것만 올린다.

    검문은 편마다 `studyez.gate`가 본다 — 막힌 편은 강의록만 나가고 덱은 미뤄진다.
    무엇을 막고 무엇을 적기만 하는지는 studyez/gate.py 첫머리에 있다.

    ## 앞에 `prequeue`가 붙는다

    쓸기 전에 `studyez prequeue`를 한 번 돌린다. 관리자가 그 사이 저장한 예습
    링크를 받아 작년 짝을 고르고 `preview.md`까지 세워 두는 일이다.
    **덱은 안 만든다** — `--build`를 안 주기 때문이고, 만드는 것은
    `scripts\nightly-prequiz.ps1`이 04:00에 한다.

    여기에도 두는 이유는 두 스크립트가 서로를 전제하지 않게 하려는 것이다.
    `prequeue`는 멱등이라(같은 링크면 내려받기를 건너뛴다) 양쪽에서 돌아도 값이
    두 번 들지 않는다. 실패해도 쓸기는 계속 간다 — 서버가 잠깐 안 뜬 것 때문에
    올릴 것이 밀리면 안 된다.

    **순서를 지키는 일 자체는 이제 `publish`가 스스로 한다.** 올리기 전에 링크를
    서버에서 당겨 오지 않으면 `preview.md`의 옛 주소를 덮어쓰는데, 그것을 이
    스크립트에만 맡기면 손으로 `publish`·`done`을 부르는 길이 열려 있었다.
    여기 남은 `prequeue`가 하는 일은 `runs/prequeue.json` — 사람이 읽는 표다.

    쓰는 법:
        powershell -File scripts\nightly-publish.ps1
        powershell -File scripts\nightly-publish.ps1 -DryRun
        powershell -File scripts\nightly-publish.ps1 -NoPrequeue
#>
[CmdletBinding()]
param(
    [string]$Python = "",
    [string]$Api = "",
    # 과목을 주면 그 과목만 훑는다. 안 주면 `--all` — 필기가 있는 과목 전부.
    [string[]]$Subject = @(),
    [switch]$DryRun,
    # 예습 링크를 받아 오는 앞 단계를 건너뛴다.
    [switch]$NoPrequeue
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$logPath = Join-Path $repo "runs\publish.log"

$logDir = Split-Path -Parent $logPath
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# 로그가 무한히 자라지 않게 5MB에서 한 번 접는다. 한 세대만 남긴다.
if (Test-Path $logPath) {
    if ((Get-Item $logPath).Length -gt 5MB) {
        Move-Item -Path $logPath -Destination "$logPath.1" -Force
    }
}

function Write-Log([string[]]$Lines) {
    $Lines | Out-File -FilePath $logPath -Append -Encoding utf8
}

# 파이썬. 이 저장소는 PATH의 python이 아니라 anaconda로 돈다 (SKILL.md와 같은 값).
if (-not $Python) {
    $candidates = @(
        (Join-Path $env:USERPROFILE "anaconda3\python.exe"),
        (Join-Path $env:USERPROFILE "miniconda3\python.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { $Python = $candidate; break }
    }
}
if (-not $Python) {
    $found = Get-Command python -ErrorAction SilentlyContinue
    if ($found) { $Python = $found.Source }
}

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
if (-not $Python) {
    Write-Log @("", ("=" * 72), "[$stamp] 파이썬을 못 찾았다 — 아무것도 올리지 않았다.",
                "  -Python 으로 경로를 주거나 PATH에 올려라.")
    exit 2
}

# 과목을 여럿 주면 과목마다 따로 부른다 — publish는 한 번에 한 과목이거나 전부다.
$targets = @()
if ($Subject.Count -gt 0) { $targets = $Subject } else { $targets = @("") }

$env:PYTHONIOENCODING = "utf-8"
$code = 0

# 저장소 안에서 파이썬을 부르고 stderr까지 로그에 담는다. 병합한 ErrorRecord가
# Stop에 걸려 스크립트를 죽이지 않도록 이 구간만 Continue로 둔다 (PowerShell 5.1).
function Invoke-Studyez([string[]]$Arguments) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Log @("", ("=" * 72), "[$stamp] $Python $($Arguments -join ' ')", ("=" * 72))

    Push-Location $repo
    try {
        $prior = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $output = & $Python @Arguments 2>&1 | ForEach-Object { $_.ToString() }
        $exit = $LASTEXITCODE
        $ErrorActionPreference = $prior
    }
    finally {
        Pop-Location
    }

    Write-Log $output
    $output | ForEach-Object { Write-Host $_ }
    return $exit
}

# 쓸기 전에 예습 링크를 받아 자리를 세운다. 실패해도 넘어간다 — 올릴 것이
# 여기에 걸려 밀리면 안 된다.
if (-not $NoPrequeue) {
    $arguments = @("-m", "studyez", "prequeue")
    if ($DryRun) { $arguments += "--dry-run" }
    if ($Api) { $arguments += @("--api", $Api) }

    $prequeueExit = Invoke-Studyez $arguments
    if ($prequeueExit -ne 0) {
        Write-Log @("[prequeue] 종료 코드 $prequeueExit — 그래도 쓸기는 계속한다")
    }
}

foreach ($target in $targets) {
    $arguments = @("-m", "studyez", "publish")
    if ($target) { $arguments += $target } else { $arguments += "--all" }
    if ($DryRun) { $arguments += "--dry-run" }
    if ($Api) { $arguments += @("--api", $Api) }

    # 한 과목이 실패해도 나머지 과목은 계속 간다. 마지막 0이 아닌 값을 남긴다.
    $exit = Invoke-Studyez $arguments
    if ($exit -ne 0) { $code = $exit }
}

$done = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
if ($code -eq 0) {
    Write-Log @("[$done] 끝 — 종료 코드 0")
}
else {
    # 실패한 편이 있으면 publish가 편마다 `✗`로 적어 놨다. 위를 보라는 뜻이다.
    Write-Log @("[$done] 끝 — 종료 코드 $code (위에 ✗ 로 적힌 편이 있다)")
}
exit $code
