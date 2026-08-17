param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("AccessKeyId", "SecretAccessKey")]
  [string]$Field
)

$ErrorActionPreference = "Stop"

$envPath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envPath)) {
  throw "server/.env 파일이 없습니다. 먼저 setup-env.ps1을 실행해 주세요."
}

$value = (Get-Clipboard -Raw).Trim()
if ($value -notmatch '^[A-Za-z0-9]{20,128}$') {
  throw "클립보드 값이 R2 키 형식과 맞지 않습니다. Cloudflare의 복사 버튼을 다시 눌러 주세요."
}

$key = if ($Field -eq "AccessKeyId") {
  "R2_ACCESS_KEY_ID"
} else {
  "R2_SECRET_ACCESS_KEY"
}

$content = [IO.File]::ReadAllText($envPath)
$pattern = "(?m)^$([regex]::Escape($key))=.*$"
$replacement = "$key=$value"

if ([regex]::IsMatch($content, $pattern)) {
  $content = [regex]::Replace($content, $pattern, $replacement, 1)
} else {
  if ($content.Length -gt 0 -and -not $content.EndsWith("`n")) {
    $content += [Environment]::NewLine
  }
  $content += $replacement + [Environment]::NewLine
}

[IO.File]::WriteAllText($envPath, $content, [Text.UTF8Encoding]::new($false))
Set-Clipboard -Value " "

Write-Host "$key saved (length: $($value.Length), clipboard cleared)" -ForegroundColor Green
