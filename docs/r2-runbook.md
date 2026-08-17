# R2 설정·키 교체 실행서

이 문서는 Claude·Codex 같은 다음 작업자가 Study_EZ 파일 저장소를 복구하거나
R2 키를 교체할 때 그대로 따라 할 수 있는 기록이다. 2026-08-17에 실제 운영
설정과 검증을 완료했다.

## 현재 운영값

| 항목 | 값 |
|---|---|
| Cloudflare 계정 ID | `d0ec59549fea0c13f1b7fe9f724df93b` |
| 버킷 | `studyez` |
| 공개 접근 | Disabled |
| 위치 | Automatic · Asia Pacific |
| Account API token | `studyez-service` |
| 권한 | Object Read & Write |
| 적용 대상 | `studyez` 버킷만 |
| Cloud Run 리비전 | `studyez-api-00003-krf` |

`meddeck-service`는 `meddeck` 버킷 전용 토큰이다. Study_EZ와 파일·키를 공유하지
않는다. `lecture_note`도 연결하려면 자기 버킷과 최소 권한 토큰을 따로 만든다.

## 새 토큰 만들기

Cloudflare → R2 Object Storage → Overview → Manage R2 API Tokens →
**Create Account API token**으로 간다.

| 설정 | 값 |
|---|---|
| Token name | `studyez-service` |
| Permissions | Object Read & Write |
| Specify bucket(s) | Apply to specific buckets only |
| Bucket | `studyez` |
| TTL | Forever |
| Client IP filtering | 비움 |

마지막 **Create Account API Token**은 외부 자격 증명을 만드는 작업이므로 자동화
작업자는 누르기 직전에 사용자 확인을 받는다.

성공 화면의 `Access Key ID`와 `Secret Access Key`는 한 번만 보인다. 이 화면을
새로고침하거나 닫기 전에 둘 다 저장한다. 위쪽의 `Token value`는 S3 자격 증명에
쓰는 값이 아니다.

## 키를 로그 없이 저장하기

브라우저의 각 복사 버튼을 누른 직후, 저장소의 `server` 디렉터리에서 실행한다.

```powershell
./set-r2-key-from-clipboard.ps1 -Field AccessKeyId
./set-r2-key-from-clipboard.ps1 -Field SecretAccessKey
```

스크립트는 클립보드 값의 형식을 검사하고 `server/.env`의 해당 줄만 바꾼다.
값 자체는 출력하지 않으며 저장 뒤 클립보드를 지운다. 성공 로그에는 필드명과
길이만 나온다. Access Key ID는 현재 32자, Secret Access Key는 64자다.

중요: 키를 일반 PowerShell 프롬프트에 직접 붙여넣으면 명령과 오류 로그에 평문으로
남는다. `setup-env.ps1`의 보안 입력창을 확실히 보고 붙여넣거나, 자동화에서는 위
클립보드 스크립트를 사용한다.

endpoint와 버킷은 다음 값이다.

```text
R2_ENDPOINT_URL=https://d0ec59549fea0c13f1b7fe9f724df93b.r2.cloudflarestorage.com
R2_BUCKET_NAME=studyez
```

## 배포

```powershell
cd server
./deploy.ps1
```

스크립트가 Secret Manager의 다음 항목을 만들거나 새 버전을 올린다.

```text
studyez-r2-access-key-id
studyez-r2-secret-access-key
```

비밀값은 배포 명령행이나 문서에 적지 않는다.

## 검증

공개 상태 확인:

```powershell
curl.exe -sS `
  "https://studyez-api-97999573571.asia-northeast3.run.app/api/health"
```

성공 응답:

```json
{"status":"ok","environment":"production"}
```

실제 R2 인증 확인은 `server`에서 실행한다. 존재하지 않는 키를 HEAD하므로 버킷
내용을 바꾸지 않는다. 인증이 성공하면 코드가 404를 `None`으로 바꿔
`R2_AUTH_OK`를 출력한다.

```powershell
./.venv/Scripts/python.exe -c "from app.storage import ObjectStorage; result=ObjectStorage().head('r2-auth-check-does-not-exist'); print('R2_AUTH_OK' if result is None else 'R2_OBJECT_EXISTS')"
```

## 키가 노출됐을 때

1. R2 API Tokens 목록에서 노출된 토큰의 메뉴 → **Delete**.
2. 토큰 이름을 다시 입력하고 삭제를 확정한다.
3. 위 절차로 새 토큰을 만든다.
4. 두 키를 클립보드 스크립트로 저장한다.
5. `deploy.ps1`로 새 Secret Manager 버전과 Cloud Run 리비전을 배포한다.
6. API와 R2 인증을 다시 검증한다.
7. 목록에 `studyez-service` 하나와 `meddeck-service`만 남았는지 확인한다.

2026-08-17 작업 중 일반 터미널에 붙여넣어진 토큰 1개와 키를 잃은 중복 토큰
2개를 모두 삭제한 뒤 최종 `studyez-service` 하나를 다시 만들었다. 노출된 키는
현재 유효하지 않다.
