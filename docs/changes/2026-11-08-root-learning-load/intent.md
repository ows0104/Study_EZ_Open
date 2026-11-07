# Intent — 뿌리 학습(Main-Quiz) 요청 지연

## 문제

2026-11-08 사용자: "지금 전체적으로 사이트의 로딩이 많이 느린거 같아. 한번 진단해줄래?"

진단(운영 Cloud Run 로그 2026-11-06~08, 요청 3,105건, 배포 revision `485c6ac`):

- 홈·시간표·정적 자산은 정상이다(시간표 0.1–0.3s, 첫 HTML 0.3s, JS 136KB br 캐시 적중).
- 느린 요청은 강의 패널의 뿌리 학습 화면(`감염과 면역/261104_02`, 11-08 01:33 KST 전후)에 몰린다.

| 요청 | 지연 | 응답 |
|---|---|---|
| `GET /api/root-learning/sessions/{id}` | 1–9s | 16KB |
| `GET /api/admin/root-learning/lectures/…` (판 목록) | 5–6s | 0KB |
| `GET /api/root-learning/lectures/…/sources/S1` (참고 PDF) | 8.8s | 22MB |
| `GET /api/admin/root-learning/lectures/…/generation` | 3–15s | 54KB |

- 같은 시각 평소 0.3s인 `/api/lectures/…`가 8.1s, `/api/health`가 3.4s였다.
  Cloud Run은 CPU 1 · uvicorn 워커 1 · concurrency 8이라 한 요청이 잡으면 다른 요청이 밀린다.

## 원하는 효과

뿌리 학습 화면을 열 때의 요청이 큰 JSON을 반복해서 옮기거나 문항마다 DB를 왕복하지 않게 해서
그 요청과, 같은 인스턴스에서 밀리던 다른 요청의 지연을 줄인다.

## 범위

- 포함: `availability()`의 문항별 개인 수정 질의, 은행 지문 재계산, 판 목록·참고 PDF 경로의 큰 칼럼 적재,
  PDF.js가 참고 PDF를 통째로 받는 동작.
- 제외: `generation` GET·관리자 폴링·Cloud Run concurrency — `claude/main-quiz-load-contention`(PR #21,
  병합됨·`cc67288b` 배포 중)이 다룬다. 사용자 2026-11-08 「Start, excluding #21」.
  `root_generation.py`·`RootGenerationPanel.tsx`·`deploy.ps1`은 건드리지 않는다.
- 제외: DB 스키마, 문항·은행·학습 기록, 학습 계획(`state`·`planning`) 계산, Cloud Run 자원 설정.
