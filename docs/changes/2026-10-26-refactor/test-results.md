# 최종 검증 결과 — 2026-10-26

검증 코드 SHA-256: `8b67d16f393e31b8b532ef0a70afdd138961e4ed97bc18ec987ca3ad73fdd2ad`.
현재 코드와 승인·검사의 연결은 state.json 및 scripts/development.py로 확인한다.

| 검사 | 결과 |
|---|---|
| 공용 계약·개발 루프·quizbank·runner pytest | 868 통과 |
| 웹 TypeScript 검사 포함 production build | 통과 |
| 웹 최신 프롬프트 전달 검사 | 6 통과 |
| Vite 개발 모드 canonical prompt import/asset HTTP | 둘 다 200 |
| 서버 bank 검사 파일별 독립 실행 | 30/31 통과, test_bank_coverage 기존 실패 1 |
| 서버 최소 배포 패키지·승인 없는 배포 중단 | 2 통과 (868에도 포함) |
| 공용 계약 wheel 빌드·독립 설치/import | 통과, schema 3.2 |
| 이동한 계약/프롬프트 원문 SHA-256 | 21파일 동일 |
| 공개 웹/API health 한 번 관측 | 정상; 로그인 후 학습·DB·큐 정상 여부를 뜻하지 않음 |

기준점에서 서버 test_bank_coverage.py:73의 상태 보존 단언이 이미 실패했고 변경 후 동일하게 실패했다.
해당 코드와 정책을 이번 경계 분리로 수정하지 않았다. `2026-10-26-bank-coverage-state` 작업에
조사 의도·설계·계획을 남겼다. 원인은 아직 확정하지 않았다.

처음 샌드박스에서는 임시 폴더 권한, 인코딩, 로컬 HTTP 실행 지연을 겪었다. TEMP/TMP·UTF-8을
명시하고 격리된 local-test DB/스토리지에서 실행했다. 러너 시간 제한 검사는 이 환경에서 통과했다.
미실행·실패를 통과로 계산하지 않았다.

동시 검사 기록 덮어쓰기 가능성을 리뷰에서 발견해 잠금과 최신 상태 병합으로 수정했고,
서로 다른 두 검사가 동시에 완료되는 회귀 검사를 추가했다. 최종 네 검사 기록이 모두 보존된다.

현재 release gate는 서버 실패 때문에 차단된다. 배포 승인도 없으며 운영 배포는 하지 않는다.
Docker 이미지 자체를 Cloud Build에서 빌드하거나 운영에 올리지는 않았다.
