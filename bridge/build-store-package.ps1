[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$SourceDirectory = $PSScriptRoot
$ReleaseDirectory = Join-Path $SourceDirectory "release"
$PackageDirectory = Join-Path $ReleaseDirectory "package"
$ManifestPath = Join-Path $SourceDirectory "manifest.json"

$Manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $ManifestPath | ConvertFrom-Json
$Version = [string]$Manifest.version
$ZipPath = Join-Path $ReleaseDirectory "studyez-preview-bridge-$Version-web-store.zip"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

if (Test-Path -LiteralPath $PackageDirectory) {
  Remove-Item -LiteralPath $PackageDirectory -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDirectory -Force | Out-Null

# 스토어 빌드에서는 로컬 개발 주소를 모두 빼 최소 권한만 남긴다.
$Manifest.host_permissions = @(
  $Manifest.host_permissions | Where-Object { $_ -notmatch '^http://(?:localhost|127\.0\.0\.1)' }
)
foreach ($Script in $Manifest.content_scripts) {
  $Script.matches = @(
    $Script.matches | Where-Object { $_ -notmatch '^http://(?:localhost|127\.0\.0\.1)' }
  )
}

# 스토어판은 학생용(사용자판)이다. 관리자 Quiz Bank의 파일 회수 스크립트는 넣지 않고,
# protocol.js의 EDITION을 user로 바꿔 자동전송·공유 링크·bank 요청을 배경에서 거절한다.
$BankScripts = @("bank-file.js", "bank-download.js")
foreach ($Script in $Manifest.content_scripts) {
  $Script.js = @($Script.js | Where-Object { $BankScripts -notcontains $_ })
}
$RuntimeFiles = @(
  "background.js",
  "chatgpt-bridge.js",
  "chatgpt-share.js",
  "provider-share.js",
  "protocol.js",
  "studyez-bridge.js"
)
foreach ($RelativePath in $RuntimeFiles) {
  Copy-Item -LiteralPath (Join-Path $SourceDirectory $RelativePath) -Destination $PackageDirectory
}

$StoreProtocolPath = Join-Path $PackageDirectory "protocol.js"
$StoreProtocol = Get-Content -Raw -Encoding UTF8 -LiteralPath $StoreProtocolPath
if ([regex]::Matches($StoreProtocol, 'EDITION: "full",').Count -ne 1) {
  throw "protocol.js에서 EDITION 표시를 찾지 못했습니다."
}
$StoreProtocol = $StoreProtocol.Replace('EDITION: "full",', 'EDITION: "user",')
[System.IO.File]::WriteAllText($StoreProtocolPath, $StoreProtocol, $Utf8NoBom)

# 배경 스크립트에도 개발 편의용 localhost 허용 분기가 있다. manifest 권한이 없어
# 스토어에서는 실행될 수 없지만 심사본에는 불필요한 코드까지 남기지 않는다.
$StoreBackgroundPath = Join-Path $PackageDirectory "background.js"
$StoreBackground = Get-Content -Raw -Encoding UTF8 -LiteralPath $StoreBackgroundPath
$StoreBackground = $StoreBackground -replace ', "http://localhost:5173"', ''
$StoreBackground = $StoreBackground -replace '(?m)^    const localOrigins = .*?\r?\n    return localOrigins.*?;\r?$', '    return false;'
if ($StoreBackground -match 'localhost|127\.0\.0\.1') {
  throw "스토어 background.js에 로컬 개발 주소가 남았습니다."
}
$ImportLine = 'importScripts("protocol.js", "bank-file.js", "bank-download.js");'
if (-not $StoreBackground.StartsWith($ImportLine)) {
  throw "background.js 첫 줄의 importScripts가 예상과 다릅니다."
}
$StoreBackground = 'importScripts("protocol.js");' + $StoreBackground.Substring($ImportLine.Length)
[System.IO.File]::WriteAllText($StoreBackgroundPath, $StoreBackground, $Utf8NoBom)

# importScripts와 content_scripts가 읽는 파일이 모두 ZIP에 있어야 한다.
# 하나라도 빠지면 서비스 워커가 시작하지 못해 확장 전체가 멈춘다.
$Referenced = @()
foreach ($Match in [regex]::Matches($StoreBackground, '(?m)^importScripts\(([^)]*)\)')) {
  $Referenced += [regex]::Matches($Match.Groups[1].Value, '"([^"]+)"') | ForEach-Object { $_.Groups[1].Value }
}
foreach ($Script in $Manifest.content_scripts) { $Referenced += @($Script.js) }
$Missing = @($Referenced | Sort-Object -Unique | Where-Object { $RuntimeFiles -notcontains $_ })
if ($Missing.Count) {
  throw "스토어 ZIP에 실행 파일이 빠졌습니다: $($Missing -join ', ')"
}

$IconDirectory = Join-Path $PackageDirectory "icons"
New-Item -ItemType Directory -Path $IconDirectory -Force | Out-Null
foreach ($Size in 16, 32, 48, 128) {
  $Name = "icon-$Size.png"
  Copy-Item -LiteralPath (Join-Path $SourceDirectory "icons\$Name") -Destination $IconDirectory
}

$StoreManifestPath = Join-Path $PackageDirectory "manifest.json"
$StoreManifestJson = $Manifest | ConvertTo-Json -Depth 20
[System.IO.File]::WriteAllText($StoreManifestPath, $StoreManifestJson, $Utf8NoBom)

$StoreManifestText = Get-Content -Raw -LiteralPath $StoreManifestPath
if ($StoreManifestText -match 'localhost|127\.0\.0\.1') {
  throw "스토어 manifest에 로컬 개발 주소가 남았습니다."
}
if ($Manifest.permissions -contains "tabs") {
  throw "스토어 manifest에 불필요한 tabs 권한이 남았습니다."
}
if ($Manifest.host_permissions -notcontains "https://d0ec59549fea0c13f1b7fe9f724df93b.r2.cloudflarestorage.com/*") {
  throw "정확한 Study EZ R2 origin이 없습니다."
}

if (Test-Path -LiteralPath $ZipPath) {
  Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path (Join-Path $PackageDirectory "*") -DestinationPath $ZipPath -CompressionLevel Optimal

$Archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
  $Names = @($Archive.Entries | ForEach-Object { $_.FullName.Replace("\", "/") })
  if ($Names -notcontains "manifest.json") {
    throw "ZIP 루트에 manifest.json이 없습니다."
  }
  if ($Names | Where-Object { $_ -match '^package/' }) {
    throw "ZIP에 불필요한 package 상위 폴더가 생겼습니다."
  }
} finally {
  $Archive.Dispose()
}

$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath).Hash.ToLowerInvariant()
Write-Host "Chrome Web Store 패키지: $ZipPath"
Write-Host "버전: $Version"
Write-Host "SHA256: $Hash"
