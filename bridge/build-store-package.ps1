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

# background.js의 importScripts와 manifest content_scripts가 읽는 파일을 모두 담는다.
# 하나라도 빠지면 서비스 워커가 시작하지 못해 확장 전체가 멈춘다. 아래에서 다시 대조한다.
$RuntimeFiles = @(
  "background.js",
  "bank-download.js",
  "bank-file.js",
  "chatgpt-bridge.js",
  "chatgpt-share.js",
  "provider-share.js",
  "protocol.js",
  "studyez-bridge.js"
)
foreach ($RelativePath in $RuntimeFiles) {
  Copy-Item -LiteralPath (Join-Path $SourceDirectory $RelativePath) -Destination $PackageDirectory
}

$BackgroundSource = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $SourceDirectory "background.js")
$Referenced = @()
foreach ($Match in [regex]::Matches($BackgroundSource, '(?m)^importScripts\(([^)]*)\)')) {
  $Referenced += [regex]::Matches($Match.Groups[1].Value, '"([^"]+)"') | ForEach-Object { $_.Groups[1].Value }
}
foreach ($Script in $Manifest.content_scripts) { $Referenced += @($Script.js) }
$Missing = @($Referenced | Sort-Object -Unique | Where-Object { $RuntimeFiles -notcontains $_ })
if ($Missing.Count) {
  throw "스토어 ZIP에 실행 파일이 빠졌습니다: $($Missing -join ', ')"
}

# 배경 스크립트에도 개발 편의용 localhost 허용 분기가 있다. manifest 권한이 없어
# 스토어에서는 실행될 수 없지만 심사본에는 불필요한 코드까지 남기지 않는다.
$StoreBackgroundPath = Join-Path $PackageDirectory "background.js"
$StoreBackground = Get-Content -Raw -Encoding UTF8 -LiteralPath $StoreBackgroundPath
$StoreBackground = $StoreBackground -replace ', "http://localhost:5173"', ''
$StoreBackground = $StoreBackground -replace '(?m)^    const localOrigins = .*?\r?\n    return localOrigins.*?;\r?$', '    return false;'
if ($StoreBackground -match 'localhost|127\.0\.0\.1') {
  throw "스토어 background.js에 로컬 개발 주소가 남았습니다."
}
[System.IO.File]::WriteAllText($StoreBackgroundPath, $StoreBackground, $Utf8NoBom)

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
