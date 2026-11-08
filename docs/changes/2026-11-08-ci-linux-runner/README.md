# GitHub Actions 사용 시간 줄이기 — 검사를 Linux로, Windows는 Windows 것만

## 의도

사용자 2026-11-08: 배포 횟수가 운영 비용을 늘리는지 물은 뒤, GitHub Actions 사용 시간이
걸림돌이라는 설명을 듣고 「Linux 러너로 진행해줘」.

근거(2026-11-08 측정):
- 저장소가 비공개라 Actions 분이 요금제 한도에서 차감되고, Windows 러너 1분은 2분으로 센다.
- `Tests and build`가 전부 `windows-latest`에서 돌았다. 한 실행 약 11–13분, 그중 서버 검사
  (`python -m tests`, 파일마다 새 프로세스)가 410–460초, Python 회귀가 약 125초.
- 11월 1–8일 실행 69회(PR 40, master push 29). 어림 계산으로 차감 약 1,500분.
  실제 사용량은 GitHub Settings → Billing에서 확인해야 한다(이 세션 권한으로는 못 읽음).

## 바꾼 것 — `.github/workflows/deploy.yml`만

1. **`checks`(Tests and build) → `ubuntu-latest`.** Windows에 묶이지 않은 검사 전부:
   Python 회귀·계약, 서버 검사, 웹 타입·빌드, bridge·배포 관문 검사, `map_numbers`,
   고정 서버 후보 준비(`prepare-build.ps1`은 pwsh로 그대로)와 업로드.
   서버는 운영(Cloud Run)이 Linux라 오히려 운영과 같은 OS에서 검사하게 된다.
   `.gitattributes`가 `eol=lf`라 후보 파일 내용은 OS와 무관하다.
2. **`windows-runner`(Windows runner checks) 새 작업 → `windows-latest`.** 운영자 Windows PC에서
   도는 것만: `tests/runner`(데스크톱 창·상태 창 포함), 바로가기 설치 확인,
   수동 배포 스크립트 검사 `tests/development/test_server_deploy.py`(Windows PowerShell),
   `tests/studyez_llm/test_codex.py`(Windows 설치 경로 분기). 이 파일들은 Linux 작업에서 빠진다
   (`test_codex.py`는 양쪽에서 돈다).
3. **배포는 두 작업을 모두 기다린다** (`needs: [checks, windows-runner]`). 배포 관문은 약해지지 않는다.
4. **같은 PR의 새 push가 이전 PR 실행을 취소한다.** master push·수동 실행은 실행마다
   별도 그룹(run_id)이라 취소되지 않는다. 배포 작업의 `studyez-production` 직렬화는 그대로.

## 바꾸지 않은 것

- **master push 때의 재검사는 남긴다.** PR 검사와 같은 일을 한 번 더 하지만, 배포 후보는
  같은 실행에서 만들고 검사한 것만 쓴다는 현행 관문(`ci_deploy.py`의 SHA·실행 ID·해시 확인)이
  거기에 기대고 있다. PR 뒤 master가 전진하면 PR 검사 대상과 병합 결과가 다를 수도 있다.
- 문서만 바뀐 커밋도 배포가 돈다. Pages 빌드가 같은 SHA의 API health를 기다리기 때문에
  API 배포를 건너뛰면 웹 배포가 막힌다.
- 서버·웹·출제 코드, DB, 운영 설정은 바꾸지 않았다.

## 기대 효과(어림)

차감 분 기준 한 실행 약 24분(12분×2) → Linux 약 8–10분 + Windows 약 4분×2 ≈ 16–18분.
PR에 연달아 push할 때 취소되는 실행만큼 더 준다. 실제 수치는 PR 실행에서 잰다(아래).

## 검사

- PR 실행에서 두 작업 모두 통과하는지, 각 단계 시간 — 결과는 `release.md`에 기록
- 로컬에는 Linux(WSL)가 없어 Linux 실행은 PR CI가 첫 확인이다

## 되돌리기

이 PR 하나를 revert하면 이전 단일 Windows 작업으로 돌아간다. 데이터·운영 상태 변경 없음.

## 결과 — PR 실행 42430301665 (두 작업 모두 success)

| | 이전(Windows 한 작업, 최근 4회) | 이번 |
|---|---|---|
| Tests and build | 약 11–13분, Windows | 297초, Linux — Python 1367 passed·2 skipped, 서버 검사 184초(이전 410–460초) |
| Windows runner checks | — | 123초 — 러너·배포스크립트·codex 751 passed, 창 검사 12+2 passed |
| 차감 분(어림) | 약 24분 | 약 5 + 2×2 ≈ 9분 |
| 걸린 시간(두 작업 병렬) | 약 12분 | 약 5분 |

PR 실행은 배포 작업을 건너뛴다(skipped, 의도대로). master 병합 실행의 검사·배포 결과는 대시보드 완료 기록에 남긴다.
