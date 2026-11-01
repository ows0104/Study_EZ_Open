# Build a new, allowlisted Cloud Run source folder. No secrets, tests or runtime data.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$target = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $target) { throw 'Destination must be a new directory.' }
New-Item -ItemType Directory -Path $target | Out-Null
foreach ($name in @('Dockerfile', 'requirements.txt')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $target
}
foreach ($entry in @(@{Source=(Join-Path $PSScriptRoot 'app'); Name='app'},
                      @{Source=(Join-Path $repo 'studyez_contracts'); Name='studyez_contracts'})) {
    $base = [IO.Path]::GetFullPath($entry.Source)
    foreach ($file in (Get-ChildItem -LiteralPath $base -File -Recurse)) {
        $relative = $file.FullName.Substring($base.Length + 1)
        if ($relative -match '(^|[\\/])(__pycache__|\.venv|build|dist|[^\\/]+\.egg-info)([\\/]|$)') { continue }
        if ($file.Extension -notin @('.py', '.json', '.toml')) { continue }
        $dest = Join-Path (Join-Path $target $entry.Name) $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $dest
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $target 'studyez_contracts/bank/schema.py'))) {
    throw 'Shared contracts are missing.'
}
Write-Output $target
