[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$SourceDirectory = $PSScriptRoot
$ReleaseDirectory = Join-Path $SourceDirectory "release"
$PackageDirectory = Join-Path $ReleaseDirectory "package"
$ManifestPath = Join-Path $SourceDirectory "manifest.json"

$Manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
$Version = [string]$Manifest.version
$ZipPath = Join-Path $ReleaseDirectory "studyez-preview-bridge-$Version-web-store.zip"

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

$RuntimeFiles = @(
  "background.js",
  "chatgpt-bridge.js",
  "chatgpt-share.js",
  "protocol.js",
  "studyez-bridge.js"
)
foreach ($RelativePath in $RuntimeFiles) {
  Copy-Item -LiteralPath (Join-Path $SourceDirectory $RelativePath) -Destination $PackageDirectory
}

$IconDirectory = Join-Path $PackageDirectory "icons"
New-Item -ItemType Directory -Path $IconDirectory -Force | Out-Null
foreach ($Size in 16, 32, 48, 128) {
  $Name = "icon-$Size.png"
  Copy-Item -LiteralPath (Join-Path $SourceDirectory "icons\$Name") -Destination $IconDirectory
}

$StoreManifestPath = Join-Path $PackageDirectory "manifest.json"
$Manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $StoreManifestPath -Encoding utf8

$StoreManifestText = Get-Content -Raw -LiteralPath $StoreManifestPath
if ($StoreManifestText -match 'localhost|127\.0\.0\.1') {
  throw "스토어 manifest에 로컬 개발 주소가 남았습니다."
}
if ($Manifest.permissions -contains "tabs") {
  throw "스토어 manifest에 불필요한 tabs 권한이 남았습니다."
}
if ($Manifest.host_permissions -notcontains "https://d0ec59549fea0c13f1b7fe9f724df93b.r2.cloudflarestorage.com/*") {
  throw "정확한 StudyEZ R2 origin이 없습니다."
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
