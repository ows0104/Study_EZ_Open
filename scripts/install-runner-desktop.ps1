<# Create a console-free desktop shortcut. Does not change login scheduled tasks. #>
[CmdletBinding()]
param([string]$Destination = [Environment]::GetFolderPath('Desktop'))
$ErrorActionPreference = 'Stop'
$runnerRepo = Split-Path -Parent $PSScriptRoot
$runnerConfig = Get-Content -LiteralPath (Join-Path $runnerRepo '.venv/pyvenv.cfg')
$runnerHome = ($runnerConfig | Where-Object { $_ -match '^home\s*=\s*(.+)$' } | Select-Object -First 1) -replace '^home\s*=\s*', ''
$runnerPython = Join-Path $runnerHome.Trim() 'pythonw.exe'
if (-not (Test-Path -LiteralPath $runnerPython)) { throw 'pythonw.exe를 찾지 못했습니다.' }
if (-not (Test-Path -LiteralPath $Destination -PathType Container)) { throw '바로가기를 둘 폴더가 없습니다.' }
$runnerShell = New-Object -ComObject WScript.Shell
$runnerShortcutPath = Join-Path $Destination 'Study EZ 러너.lnk'
$runnerShortcut = $runnerShell.CreateShortcut($runnerShortcutPath)
$runnerShortcut.TargetPath = $runnerPython
$runnerShortcut.Arguments = '-m runner.desktop'
$runnerShortcut.WorkingDirectory = $runnerRepo
$runnerShortcut.Description = '강의별 예습·복습 시작, 중지, 취소와 전체 일시정지. 입력이 없으면 1분 뒤 자동 시작.'
$runnerShortcut.IconLocation = "$runnerPython,0"
$runnerShortcut.Save()
if (-not (Test-Path -LiteralPath $runnerShortcutPath -PathType Leaf)) { throw '바로가기를 저장하지 못했습니다.' }
Write-Output $runnerShortcutPath
