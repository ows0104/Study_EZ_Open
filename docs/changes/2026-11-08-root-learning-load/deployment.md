# 배포 — 뿌리 학습 요청 지연

## 승인과 경로

- 2026-11-08 사용자 「Merge and deploy」 — PR #24 병합(=운영 자동 배포) 승인.
- PR #24 `Tests and build` 통과(11m35s) 뒤 병합: merge commit `13956805`.
- 그 run(42395569591)의 API 배포는 「superseded by a newer master commit」으로 스스로 멈췄다. 바로 뒤에 PR #25(`claude/root-generation-columns`)·#26(`claude/approval-scope`)가 병합되었기 때문이다. 정상 동작이다.
- `c8133cec`(PR #24·#25·#26 포함) run 42396617930: `Tests and build` 성공, `Deploy production API` 성공.

## 반영 확인 (2026-11-07 17:4x UTC = 11-08 02:4x KST)

| 확인 | 결과 |
|---|---|
| 운영 `/api/health` | `revision: c8133cec613d775da631b5ad33925f957eb0b4f4` |
| Cloud Run 트래픽 | `studyez-api-release-423966179301` 100%, concurrency 8 |
| 배포 사후 검사 요청 | `/api/me`·`/api/timetable`·`/api/spotter/db`·`…/generation` 모두 401 (인증 없는 검사, 기대값) |
| Pages 웹 | `studyez.kr` → `assets/index-BSrG-2vM.js` → `RootPdfSlides-Df6Z6R2s.js`에 `disableStream:!0,disableAutoFetch:!0,rangeChunkSize:524288` |

## 수정 전 기준 (운영 로그 2026-11-06 00:00 – 11-07 16:40 UTC, revision `485c6ac` 이전)

| 요청 | n | 중앙 | p90 | 최대 | 최대 응답 |
|---|---|---|---|---|---|
| `GET /api/root-learning/sessions/{id}` | 30 | 1.28s | 3.86s | 8.9s | 0.02MB |
| `GET /api/admin/root-learning/lectures/{s}/{r}` (판 목록) | 9 | 2.09s | 5.72s | 5.7s | 0MB |
| `GET /api/root-learning/lectures/{s}/{r}` (개요) | 31 | 0.25s | 0.78s | 7.3s | 0.03MB |
| `POST …/sessions` | 5 | 1.07s | 1.83s | 1.8s | 0MB |
| `GET /api/root-learning` | 5 | 0.04s | 1.86s | 1.9s | 0.03MB |
| `GET …/sources/{id}` (참고 PDF) | 4 | 2.53s | 8.84s | 8.8s | 22.75MB |

## 수정 뒤

**아직 측정하지 못했다.** 배포 직후 새벽이라 실제 사용자 요청이 없었다(위 401 검사뿐).
실제 사용 뒤 같은 표를 revision `studyez-api-release-423966179301` 이후 구간으로 다시 만들어 여기에 붙인다.
#25(관리자 generation GET)가 같은 배포에 들어 있으므로 generation GET은 이 변경의 효과로 세지 않는다.
개선이 확인되기 전에는 성공으로 적지 않는다.
