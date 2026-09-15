# Study_EZ 서버를 Cloud Run에 올린다.
#
#     ./deploy.ps1
#
# `.env`를 읽어 비밀값은 Secret Manager로, 나머지는 평범한 환경 변수로 넘긴다.
# **비밀값은 화면에도 배포 명령에도 나오지 않는다** — `gcloud run deploy`에
# 직접 실으면 배포 이력과 셸 기록에 그대로 남는다.
#
# 컨테이너는 Cloud Build가 만든다. 로컬에 Docker가 없어도 된다.

# PowerShell 5.1은 네이티브 명령이 stderr에 쓴 줄을 오류 레코드로 감싼다.
# gcloud는 경고도 빌드 로그도 전부 stderr로 내보내므로, "Stop"으로 두면 멀쩡한
# 배포가 첫 경고에서 멈춘다. 대신 중요한 호출마다 종료 코드를 직접 본다.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

function Assert-Ok([string]$what) {
  if ($LASTEXITCODE -ne 0) { throw "$what 실패 (종료 코드 $LASTEXITCODE)" }
}

$PROJECT = "meddeck-503318"
$REGION  = "asia-northeast3"
$SERVICE = "studyez-api"

# Secret Manager로 갈 것. 나머지는 평문 환경 변수다.
$SECRET_KEYS = @(
  "DATABASE_URL",
  "SUPABASE_JWT_SECRET",
  "R2_ACCESS_KEY_ID",
  "R2_SECRET_ACCESS_KEY",
  "RUNNER_TOKEN"
)

# ── .env 읽기 ────────────────────────────────────────────────────────
# .NET의 작업 디렉터리는 Set-Location을 따라오지 않는다. 절대경로로 준다.
$ENV_PATH = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $ENV_PATH)) { throw ".env가 없습니다. .env.example을 보고 만들어 주세요." }

$env_values = @{}
foreach ($line in [IO.File]::ReadAllLines($ENV_PATH)) {
  if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
  $pair = $line -split '=', 2
  $env_values[$pair[0].Trim()] = $pair[1].Trim()
}

# 비어도 되는 것. 나머지는 비어 있으면 안 된다.
#
# SUPABASE_JWT_SECRET을 비우면 JWKS로 RS256을 검증한다. 요즘 Supabase는
# 비대칭 키가 기본이라 그 편이 정석이고 비밀값을 하나 덜 다루게 된다.
# CORS는 프론트를 같은 도메인에 두면 필요 없다.
#
# R2도 없어도 뜬다. 캘린더·로그인·승인·강의 목록은 파일이 하나도 없어도 돌고,
# 파이프라인 산출물은 나중에 올라온다. 붙기 전까지 파일 경로만 503으로 답한다.
$OPTIONAL = @(
  "SUPABASE_JWT_SECRET", "CORS_ALLOWED_ORIGINS",
  "R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"
)

# 안 채운 자리를 먼저 잡는다. 반쯤 설정된 채로 배포되면 500이 나고서야 안다.
$blank = $env_values.GetEnumerator() |
  Where-Object { $_.Value -match '^<.*>$' -or ($_.Value -eq '' -and $OPTIONAL -notcontains $_.Key) } |
  ForEach-Object { $_.Key }
if ($blank) {
  throw "`.env`에서 아직 안 채운 값이 있습니다:`n  " + ($blank -join "`n  ")
}

# ── 비밀값을 Secret Manager로 ────────────────────────────────────────
# 값은 임시 파일로만 건넨다. 파이프로 넘기면 PowerShell이 끝에 줄바꿈을 붙여
# 토큰이 한 글자 길어지고, 그러면 인증이 조용히 실패한다.
# 있는 비밀을 한 번에 가져온다. `--filter`를 걸면 결과가 비었을 때 gcloud가
# "filter keys were not present" 경고를 stderr로 뱉는다. 거르는 일은 여기서 한다.
$existing = @(gcloud secrets list --project $PROJECT --format "value(name)")
Assert-Ok "비밀 목록 조회"

function Sync-Secret([string]$name, [string]$value) {
  if (-not ($existing -contains $name)) {
    gcloud secrets create $name --project $PROJECT --replication-policy=automatic | Out-Null
    Assert-Ok "비밀 $name 생성"
  }
  $tmp = [IO.Path]::GetTempFileName()
  try {
    [IO.File]::WriteAllText($tmp, $value, (New-Object Text.UTF8Encoding $false))
    gcloud secrets versions add $name --project $PROJECT --data-file=$tmp | Out-Null
    Assert-Ok "비밀 $name 저장"
  } finally {
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  }
}

# 비어 있는 것은 아예 올리지 않는다. Secret Manager가 빈 payload를 거부하기도
# 하지만, 그보다 참조하지 않는 편이 맞다 — JWT Secret을 안 주면 JWKS로,
# R2를 안 주면 파일 경로만 잠긴 채로 도는 것이 의도한 동작이다.
$active = @($SECRET_KEYS | Where-Object { $env_values[$_] })

Write-Host "비밀값을 Secret Manager에 올립니다..."
foreach ($key in $active) {
  Sync-Secret "studyez-$($key.ToLower().Replace('_','-'))" $env_values[$key]
  Write-Host "  $key"
}
$skipped = @($SECRET_KEYS | Where-Object { -not $env_values[$_] })
if ($skipped) { Write-Host "  건너뜀(비어 있음): $($skipped -join ', ')" -ForegroundColor DarkGray }

# Cloud Run 기본 서비스 계정이 비밀을 읽을 수 있어야 한다.
$PROJECT_NUMBER = (gcloud projects describe $PROJECT --format="value(projectNumber)")
Assert-Ok "프로젝트 번호 조회"
$RUNTIME_SA = "$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
foreach ($key in $active) {
  gcloud secrets add-iam-policy-binding "studyez-$($key.ToLower().Replace('_','-'))" `
    --project $PROJECT --member "serviceAccount:$RUNTIME_SA" `
    --role roles/secretmanager.secretAccessor 2>$null | Out-Null
}

# ── 배포 ─────────────────────────────────────────────────────────────
$plain = @(
  "ENVIRONMENT=$($env_values['ENVIRONMENT'])",
  "SUPABASE_URL=$($env_values['SUPABASE_URL'])",
  "R2_ENDPOINT_URL=$($env_values['R2_ENDPOINT_URL'])",
  "R2_BUCKET_NAME=$($env_values['R2_BUCKET_NAME'])",
  "STUDYEZ_ADMIN_EMAILS=$($env_values['STUDYEZ_ADMIN_EMAILS'])",
  "STUDYEZ_SHOW_CONVERSATION_URL=$($env_values['STUDYEZ_SHOW_CONVERSATION_URL'])",
  "STUDYEZ_SIGNED_URL_TTL=$($env_values['STUDYEZ_SIGNED_URL_TTL'])",
  "STUDYEZ_MAX_UPLOAD_MB=$($env_values['STUDYEZ_MAX_UPLOAD_MB'])",
  "CORS_ALLOWED_ORIGINS=$($env_values['CORS_ALLOWED_ORIGINS'])"
) -join "|"

$secrets = ($active | ForEach-Object {
  "$_=studyez-$($_.ToLower().Replace('_','-')):latest"
}) -join ","

Write-Host "`nCloud Run에 배포합니다 ($SERVICE / $REGION)..."
# 구분자를 쉼표에서 |로 바꾼다(`^구분자^목록` 형식). 관리자 메일 목록과 CORS
# 주소에 쉼표가 들어 있어 기본값으로 두면 값이 거기서 잘린다. @는 못 쓴다 —
# 메일 주소에 들어 있다.
gcloud run deploy $SERVICE `
  --project $PROJECT `
  --region $REGION `
  --source . `
  --allow-unauthenticated `
  --set-env-vars "^|^$plain" `
  --set-secrets $secrets `
  --cpu 1 --memory 512Mi `
  --min-instances 0 --max-instances 4 `
  --timeout 600
Assert-Ok "Cloud Run 배포"

$url = gcloud run services describe $SERVICE --project $PROJECT --region $REGION --format="value(status.url)"
Assert-Ok "서비스 주소 조회"
Write-Host "`n배포 완료: $url"
Write-Host "확인: curl $url/api/health"
