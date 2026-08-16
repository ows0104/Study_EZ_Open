# 대시보드에서 받은 값을 .env 두 개에 넣는다.
#
#     ./setup-env.ps1
#
# 값을 물어보고 형식을 검사한 뒤 `server/.env`와 `web/.env.production`에 쓴다.
# 비밀값은 입력할 때 화면에 찍히지 않고, 다 넣은 뒤에도 되보여 주지 않는다.
#
# 이미 채워진 값은 그대로 두고 넘어간다. 한 곳만 고치고 싶을 때 다시 돌리면 된다.

$ErrorActionPreference = "Stop"

$SERVER_ENV = Join-Path $PSScriptRoot ".env"
$WEB_ENV = Join-Path (Split-Path $PSScriptRoot -Parent) "web\.env.production"

function Read-Value {
  param(
    [string]$Key,
    [string]$Where,      # 대시보드 어디서 가져오는 값인가
    [string]$Pattern,    # 형식 검사
    [string]$Hint,       # 형식이 틀렸을 때 알려 줄 말
    [switch]$Secret,
    [switch]$Optional
  )
  Write-Host ""
  Write-Host "  $Key" -ForegroundColor Cyan
  Write-Host "  $Where" -ForegroundColor DarkGray
  if ($Optional) { Write-Host "  (비워 두고 Enter를 눌러도 됩니다)" -ForegroundColor DarkGray }

  while ($true) {
    if ($Secret) {
      # 어깨너머로 보이지 않게. 값은 파일로만 간다.
      $secure = Read-Host "  값" -AsSecureString
      $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
      try { $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
      finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    } else {
      $value = Read-Host "  값"
    }
    $value = $value.Trim()

    if (-not $value) {
      if ($Optional) { return "" }
      Write-Host "  비울 수 없는 값입니다." -ForegroundColor Yellow
      continue
    }
    if ($Pattern -and $value -notmatch $Pattern) {
      Write-Host "  $Hint" -ForegroundColor Yellow
      continue
    }
    return $value
  }
}

# ── 기존 값 읽기 ─────────────────────────────────────────────────────
$current = @{}
if (Test-Path $SERVER_ENV) {
  foreach ($line in [IO.File]::ReadAllLines($SERVER_ENV)) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
    $pair = $line -split '=', 2
    $current[$pair[0].Trim()] = $pair[1].Trim()
  }
}
function Is-Blank($key) {
  return (-not $current.ContainsKey($key)) -or ($current[$key] -match '^<.*>$')
}

Write-Host ""
Write-Host "Study_EZ 설정" -ForegroundColor White
Write-Host "채울 곳만 물어봅니다. 이미 넣은 값은 건너뜁니다." -ForegroundColor DarkGray

# ── Supabase ─────────────────────────────────────────────────────────
if (Is-Blank "SUPABASE_URL") {
  $current["SUPABASE_URL"] = Read-Value -Key "SUPABASE_URL" `
    -Where "Supabase → Project Settings → Data API → Project URL" `
    -Pattern '^https://[a-z0-9-]+\.supabase\.co/?$' `
    -Hint "https://xxxxxxxx.supabase.co 모양이어야 합니다."
  $current["SUPABASE_URL"] = $current["SUPABASE_URL"].TrimEnd('/')
}

if (Is-Blank "DATABASE_URL") {
  $current["DATABASE_URL"] = Read-Value -Key "DATABASE_URL" -Secret `
    -Where "Project Settings → Database → Connection string → URI (Transaction pooler, 6543)" `
    -Pattern '^postgres(ql)?://.+:.+@.+:\d+/\w+' `
    -Hint "postgresql://사용자:비밀번호@호스트:6543/postgres 모양이어야 합니다."
  if ($current["DATABASE_URL"] -notmatch ':6543/') {
    # Session pooler(5432)는 연결을 오래 붙든다. Cloud Run은 컨테이너가 수시로
    # 뜨고 져서 그쪽을 쓰면 연결이 금방 바닥난다.
    Write-Host "  경고: 6543이 아닙니다. Transaction pooler가 맞는지 확인해 주세요." -ForegroundColor Yellow
  }
  if ($current["DATABASE_URL"] -match '\[YOUR-PASSWORD\]') {
    throw "[YOUR-PASSWORD] 자리를 실제 비밀번호로 바꿔서 넣어 주세요."
  }
}

# 비워 두면 JWKS로 RS256 검증을 한다. 요즘 Supabase 기본이 비대칭 키라
# 그 편이 정석이고, 비밀값을 하나 덜 다루게 된다.
if (Is-Blank "SUPABASE_JWT_SECRET") {
  $current["SUPABASE_JWT_SECRET"] = Read-Value -Key "SUPABASE_JWT_SECRET" -Secret -Optional `
    -Where "비워 두는 것을 권합니다. 그러면 JWKS로 검증합니다(Supabase 기본인 비대칭 키)."
}

# ── R2 ───────────────────────────────────────────────────────────────
if (Is-Blank "R2_ENDPOINT_URL") {
  $current["R2_ENDPOINT_URL"] = Read-Value -Key "R2_ENDPOINT_URL" `
    -Where "Cloudflare → R2 → 버킷 → Settings → S3 API 주소 (끝의 /버킷이름은 뗍니다)" `
    -Pattern '^https://[a-f0-9]+\.r2\.cloudflarestorage\.com/?$' `
    -Hint "https://<계정ID>.r2.cloudflarestorage.com 모양이어야 합니다. 뒤에 버킷 이름이 붙어 있으면 떼 주세요."
  $current["R2_ENDPOINT_URL"] = $current["R2_ENDPOINT_URL"].TrimEnd('/')
}

if (Is-Blank "R2_ACCESS_KEY_ID") {
  $current["R2_ACCESS_KEY_ID"] = Read-Value -Key "R2_ACCESS_KEY_ID" -Secret `
    -Where "R2 → API → Manage API tokens → Create (Object Read & Write, studyez 버킷만)" `
    -Pattern '^\S{16,}$' -Hint "너무 짧습니다. 다시 확인해 주세요."
}

if (Is-Blank "R2_SECRET_ACCESS_KEY") {
  $current["R2_SECRET_ACCESS_KEY"] = Read-Value -Key "R2_SECRET_ACCESS_KEY" -Secret `
    -Where "위와 같은 화면. 한 번만 보이는 값입니다." `
    -Pattern '^\S{32,}$' -Hint "너무 짧습니다. Access Key ID가 아니라 Secret 쪽이 맞는지 확인해 주세요."
}

# ── server/.env 쓰기 ─────────────────────────────────────────────────
$lines = [IO.File]::ReadAllLines($SERVER_ENV)
$out = foreach ($line in $lines) {
  if ($line -match '^\s*#' -or $line -notmatch '=') { $line; continue }
  $key = ($line -split '=', 2)[0].Trim()
  if ($current.ContainsKey($key)) { "$key=$($current[$key])" } else { $line }
}
[IO.File]::WriteAllLines($SERVER_ENV, $out, (New-Object Text.UTF8Encoding $false))
Write-Host "`n  server/.env 저장했습니다." -ForegroundColor Green

# ── web/.env.production 쓰기 ─────────────────────────────────────────
$web = @{}
if (Test-Path $WEB_ENV) {
  foreach ($line in [IO.File]::ReadAllLines($WEB_ENV)) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
    $pair = $line -split '=', 2
    $web[$pair[0].Trim()] = $pair[1].Trim()
  }
}

# Supabase URL은 서버 쪽에서 그대로 가져온다. 두 번 물어볼 이유가 없다.
$web["VITE_SUPABASE_URL"] = $current["SUPABASE_URL"]

if ((-not $web.ContainsKey("VITE_SUPABASE_ANON_KEY")) -or ($web["VITE_SUPABASE_ANON_KEY"] -match '^<.*>$')) {
  # anon 키는 브라우저 번들에 그대로 들어가는 공개 값이라 가리지 않는다.
  $web["VITE_SUPABASE_ANON_KEY"] = Read-Value -Key "VITE_SUPABASE_ANON_KEY" `
    -Where "Supabase → Project Settings → API Keys → anon / public" `
    -Pattern '^\S{20,}$' -Hint "너무 짧습니다. service_role이 아니라 anon 키입니다."
}

if ((-not $web.ContainsKey("VITE_API_BASE_URL")) -or ($web["VITE_API_BASE_URL"] -match '^<.*>$')) {
  # Cloud Run 배포 전에는 주소를 모른다. 나중에 채워도 된다.
  $web["VITE_API_BASE_URL"] = ""
}

$web_out = @(
  "# 배포 빌드용. 커밋되지 않는다. setup-env.ps1이 씁니다.",
  "#",
  "# anon 키는 브라우저 번들에 들어가는, 공개돼도 되는 값이다. 실제 권한은",
  "# 서버의 JWT 검증과 승인 게이트가 정한다.",
  "",
  "VITE_SUPABASE_URL=$($web['VITE_SUPABASE_URL'])",
  "VITE_SUPABASE_ANON_KEY=$($web['VITE_SUPABASE_ANON_KEY'])",
  "",
  "# Cloud Run 주소. deploy.ps1 을 돌린 뒤 채웁니다.",
  "VITE_API_BASE_URL=$($web['VITE_API_BASE_URL'])"
)
[IO.File]::WriteAllLines($WEB_ENV, $web_out, (New-Object Text.UTF8Encoding $false))
Write-Host "  web/.env.production 저장했습니다." -ForegroundColor Green

Write-Host "`n다 됐습니다. 이제 스키마를 만들고 배포하면 됩니다:" -ForegroundColor White
Write-Host "  .venv\Scripts\python.exe -m app.cli init-db"
Write-Host "  .\deploy.ps1"
