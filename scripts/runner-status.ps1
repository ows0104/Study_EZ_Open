<# Show an already running agent. This script never starts or stops a runner. #>
[CmdletBinding()]
param(
    [int]$IntervalSeconds = 5,
    [switch]$Once,
    [switch]$Console
)

$ErrorActionPreference = 'Stop'
$monitorRepo = Split-Path -Parent $PSScriptRoot
$monitorRuns = Join-Path $monitorRepo 'runs'
if (-not $Console -and -not $Once) {
    # uv 가상환경의 pythonw 프록시는 콘솔용 python.exe를 자식으로 띄울 수 있다.
    # 상태 창은 표준 라이브러리만 쓰므로 기본 설치의 실제 pythonw.exe를 직접 쓴다.
    $monitorPython = @(
        foreach ($monitorConfig in @('.venv/pyvenv.cfg', 'server/.venv/pyvenv.cfg')) {
            $monitorConfigPath = Join-Path $monitorRepo $monitorConfig
            if (Test-Path -LiteralPath $monitorConfigPath) {
                foreach ($monitorConfigLine in (Get-Content -LiteralPath $monitorConfigPath)) {
                    if ($monitorConfigLine -match '^home\s*=\s*(.+)$') {
                        Join-Path $Matches[1].Trim() 'pythonw.exe'
                    }
                }
            }
        }
        (Join-Path $env:USERPROFILE 'anaconda3/pythonw.exe')
        (Join-Path $env:USERPROFILE 'miniconda3/pythonw.exe')
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $monitorPython) { throw 'pythonw.exe를 찾지 못했습니다. -Console로 텍스트 상태를 볼 수 있습니다.' }
    Write-Verbose "상태 창: $monitorPython (기존 러너는 유지)"
    Start-Process -FilePath $monitorPython -WorkingDirectory $monitorRepo -WindowStyle Normal `
        -ArgumentList @('-m', 'runner.status_window', '--interval', [Math]::Max(1, $IntervalSeconds))
    return
}
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = 'Study EZ - Runner Live Status'

function Format-MonitorLine([string]$Text) {
    if ($Text.Length -gt 260) { return $Text.Substring(0, 260) + ' … (전체 내용은 로그 파일)' }
    return $Text
}

do {
    $monitorLines = [Collections.Generic.List[string]]::new()
    $monitorLines.Add('Study EZ 러너 실시간 상태')
    $monitorLines.Add(('확인 시각: {0:yyyy-MM-dd HH:mm:ss} | {1}초마다 갱신' -f (Get-Date), $IntervalSeconds))
    $monitorLines.Add('이 창은 상태만 표시합니다. 닫아도 러너와 생성 작업은 계속됩니다.')
    $monitorLines.Add('')
    $monitorLock = Get-Item -LiteralPath (Join-Path $monitorRuns 'agent.lock') -ErrorAction SilentlyContinue
    $monitorAgentId = 0
    if ($monitorLock) {
        $monitorLockText = Get-Content -LiteralPath $monitorLock.FullName -Raw -Encoding UTF8
        if ($monitorLockText -match 'pid\s+(\d+)') { $monitorAgentId = [int]$Matches[1] }
    }
    $monitorProcesses = @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='codex.exe'")
    $monitorAgent = $monitorProcesses | Where-Object { $_.ProcessId -eq $monitorAgentId -and $_.CommandLine -match '-m runner agent' }
    if ($monitorAgent) {
        $monitorAge = [int]((Get-Date) - $monitorLock.LastWriteTime).TotalSeconds
        $monitorLines.Add(('러너 실행 중 | PID {0} | 마지막 생존 표시 {1}초 전' -f $monitorAgentId, $monitorAge))
        if ($monitorAge -gt 90) { $monitorLines.Add('주의: 생존 표시가 90초 넘게 갱신되지 않았습니다.') }
        $monitorJobs = @($monitorProcesses | Where-Object {
            $_.ParentProcessId -eq $monitorAgentId -and $_.CommandLine -match '-m runner bank'
        })
        $monitorLines.Add(('실행 중인 퀴즈 작업: {0}개' -f $monitorJobs.Count))
        foreach ($monitorJob in $monitorJobs) {
            if ($monitorJob.CommandLine -notmatch '--run-id\s+(\S+)') { continue }
            $monitorRunId = $Matches[1].Trim('"')
            $monitorKind = if ($monitorJob.CommandLine -match '--points-only') { '출제포인트 준비' } else { '퀴즈 생성·검수' }
            $monitorName = $monitorRunId
            $monitorSource = Join-Path $monitorRuns "$monitorRunId/source.json"
            if (Test-Path -LiteralPath $monitorSource) {
                $monitorInfo = Get-Content -LiteralPath $monitorSource -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($monitorInfo.stem) { $monitorName = $monitorInfo.stem }
            }
            $monitorJobLog = Get-Item -LiteralPath (Join-Path $monitorRuns "agent.$monitorRunId.log") -ErrorAction SilentlyContinue
            $monitorLines.Add('')
            $monitorLines.Add(('  {0} | {1}' -f $monitorName, $monitorKind))
            if ($monitorJobLog) {
                $monitorTail = @(Get-Content -LiteralPath $monitorJobLog.FullName -Tail 20 -Encoding UTF8)
                $monitorStage = @($monitorTail | Where-Object { $_ -match '^── ' } | Select-Object -Last 1)
                if ($monitorStage.Count) { $monitorLines.Add(('  현재 단계: {0}' -f ($monitorStage[0] -replace '^── ', ''))) }
                $monitorLogAge = [int]((Get-Date) - $monitorJobLog.LastWriteTime).TotalSeconds
                $monitorLines.Add(('  단계 로그 갱신: {0}초 전 (한 CLI 단계는 수 분 걸릴 수 있습니다)' -f $monitorLogAge))
                foreach ($monitorLine in ($monitorTail | Select-Object -Last 4)) { $monitorLines.Add(('    {0}' -f (Format-MonitorLine $monitorLine))) }
            }
        }
        if (-not $monitorJobs.Count) { $monitorLines.Add('현재 퀴즈 하위 프로세스는 없습니다. 대기 또는 자료 동기화 중입니다.') }
    }
    else { $monitorLines.Add('실행 중인 러너를 확인하지 못했습니다. 새 러너를 자동으로 시작하지 않습니다.') }
    $monitorLines.Add('')
    $monitorLines.Add('최근 러너 전체 로그:')
    $monitorMainLog = Join-Path $monitorRuns 'agent.log'
    if (Test-Path -LiteralPath $monitorMainLog) {
        foreach ($monitorLine in (Get-Content -LiteralPath $monitorMainLog -Tail 5 -Encoding UTF8)) { $monitorLines.Add((Format-MonitorLine $monitorLine)) }
    }
    if (-not $Once) { Clear-Host }
    $monitorLines | ForEach-Object { Write-Host $_ }
    if (-not $Once) { Start-Sleep -Seconds ([Math]::Max(1, $IntervalSeconds)) }
} while (-not $Once)
