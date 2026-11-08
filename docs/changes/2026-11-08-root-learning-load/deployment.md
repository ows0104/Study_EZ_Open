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

## 수정 뒤 (운영 로그 2026-11-07 17:40 – 11-08 14:26 UTC, 2026-11-08 자동 재측정)

방법: `gcloud logging read`(읽기 전용) `service_name="studyez-api" AND requestUrl:"/api/"`, 2,014건.
401·OPTIONS·`/api/health`를 빼고 879건. 경로는 URL 디코드 뒤 판정. `/generation`은 #25 변경이라 뺐다.
지연은 Cloud Run `httpRequest.latency`. p90은 nearest-rank. 「표본 부족」은 분류당 5건 미만.

### 수정 전 → 수정 뒤 (배포 뒤 모든 revision 합산)

| 요청 | 전 n | 전 중앙 | 전 p90 | 전 최대 | 뒤 n | 뒤 중앙 | 뒤 p90 | 뒤 최대 | 뒤 최대 응답 | 판정 |
|---|---|---|---|---|---|---|---|---|---|---|
| `GET /api/root-learning/sessions/{id}` | 30 | 1.28s | 3.86s | 8.9s | 19 | 1.06s | 3.05s | 3.3s | 0.02MB | 꼬리만 줄었다. 중앙 1s·p90 3s가 남았다 |
| `GET /api/admin/root-learning/lectures/{s}/{r}` (판 목록) | 9 | 2.09s | 5.72s | 5.7s | 9 | 1.35s | 2.59s | 2.6s | 0MB | 개선, 여전히 1s 넘음 |
| `GET /api/root-learning/lectures/{s}/{r}` (개요) | 31 | 0.25s | 0.78s | 7.3s | 15 | 0.41s | 0.59s | 0.8s | 0.03MB | 최대 사라짐, 중앙은 조금 늘었다 |
| `POST …/sessions` | 5 | 1.07s | 1.83s | 1.8s | 3 | 0.44s | 1.04s | 1.0s | 0MB | **표본 부족 — 결론 보류** |
| `GET /api/root-learning` | 5 | 0.04s | 1.86s | 1.9s | 5 | 0.62s | 1.07s | 1.1s | 0.03MB | 표본 경계(5건), 판단 못 함 |
| `GET …/sources/{id}` (참고 PDF) | 4 | 2.53s | 8.84s | 8.8s | 29 | 0.43s | 1.68s | 2.0s | 22.75MB | 범위 요청으로 바뀌었다(아래) |

참고 PDF: 29건 중 206 27건(93%), 200 2건, 합계 58.6MB.
22.75MB 전체 200은 11-07 17:53, 18:18 두 번뿐이고 둘 다 첫 두 revision(배포 직후 1시간 안)이다.
11-08 00:59 이후 열람 4회(25건)는 모두 206, 응답 0.2–1.05MB(대부분 512KB 청크), 요청당 0.34–2.0s.
첫 200 두 건은 배포 전 캐시된 웹 번들이 열었을 수 있다(추정, 확인 안 함).

### 같은 시각 다른 요청

느린 sessions GET·판 목록 앞뒤 10초의 `/api/me`·`/api/lectures/…`·`/api/timetable`은 0.03–0.96s였다.
같이 느려지지 않았다. 구간 전체로도 `/api/me` n41 중앙 0.07s p90 0.71s, `/api/lectures/…` n63 0.18s 0.31s, `/api/timetable` n95 0.14s 0.69s.
느린 요청 중 인스턴스 시작 20초 안은 sessions GET 1건뿐이라 콜드 스타트로 설명되지 않는다.
판 목록·sessions GET은 같은 화면의 관리자 `…/generation` GET(55KB, 2.3–4.9s, 12:03에는 500 두 번)과 같은 순간에 들어온다.

### revision별 (뿌리 학습 요청이 있던 것만)

배포가 이어져 revision 17개가 지나갔다. 아래 SHA는 master 배포 run 종료 시각으로 맞춘 것이다.
Cloud Run의 `git-sha` 라벨은 모든 revision에서 `fa1f8508`로 고정이라 쓸 수 없었다.
현재 운영 `/api/health` revision은 `d1ae1c19896a8079121be30966c6d2eb96c32915`(`studyez-api-release-424766595861`).

| revision | master | sessions GET n·중앙·p90 | 판 목록 n | 개요 n | POST n | 목록 n | sources n (최대 응답) |
|---|---|---|---|---|---|---|---|
| `…423966179301` | `c8133cec` | 2 · 0.99s · 1.68s | 1 | 2 | 0 | 0 | 5 (22.75MB) |
| `…423994686331` | `8d583535` | 5 · 1.22s · 3.05s | 2 | 6 | 2 | 0 | 4 (22.75MB) |
| `…424313590281` | `675a59e7` | 5 · 1.04s · 1.73s | 2 | 2 | 0 | 3 | 5 (1.05MB) |
| `…424398276031` | `cabeb38f` | 3 · 1.06s · 2.29s | 2 | 2 | 0 | 1 | 9 (0.52MB) |
| `…424454134921` | `791ac589` | 1 · 3.34s | 1 | 1 | 0 | 0 | 6 (0.52MB) |
| `…424472530381` | `bfa0da3a` | 1 · 2.87s | 0 | 0 | 0 | 0 | 0 |
| `…424766595861` | `d1ae1c19` | 2 · 0.59s · 0.93s | 1 | 2 | 1 | 1 | 0 |

revision 하나당 표본이 1–6건이라 revision 간 비교는 하지 않는다.
`c8133cec` 뒤 master에서 `server/app/routes/root_learning.py`가 +199줄 바뀌었다. 합산 수치는 #24만의 효과가 아니다.

### 결론

- 참고 PDF: **개선 확인.** 첫 화면이 22.75MB 전체 대신 512KB 범위 요청으로 열린다. 중앙 2.53s → 0.43s.
- 꼬리 지연: 모든 분류에서 최대가 7–9s → 3.3s 이하로 줄었다.
- sessions GET: **개선 미흡.** 중앙 1.28s → 1.06s, p90 3.86s → 3.05s. 같은 순간 `/api/me`는 빠르다.
- POST sessions·`GET /api/root-learning`: 표본 부족 — 결론 보류.

남은 원인 후보(확인 안 함):
1. sessions GET 안의 DB 왕복·조립이 아직 남아 있다(응답은 12–19KB로 작다).
2. 같은 화면의 `…/generation` GET(2–5s)이 같은 인스턴스(concurrency 8)·DB 연결을 동시에 쓴다.
3. Cloud Run–DB 사이 왕복 지연이 쿼리 수만큼 곱해진다.
