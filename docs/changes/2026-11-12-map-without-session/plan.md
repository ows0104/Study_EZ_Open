# Main-Quiz 개념 지도 회차 분리 — 구현 계획

승인: 사용자 요청(2026-11-12) 「네, 진행」·「함수 달라서 병행」이 이 범위의 구현 지시. 배포는 되돌릴 수 있는 코드 배포(DB 스키마 변경 없음).

## 변경 범위·대상 파일·순서
1. `server/app/routes/root_learning.py`: `map_payload` 추출, `POST BASE/map`(`lecture_map`), `start()` fresh state의 `mapSeen` 승계.
2. `server/tests/test_root_lecture_map.py`: 과제 0개·목록 완료에서 지도 200, 같은 날 반복 열람 행 1개, 열람 뒤 새 회차 `mapSeen=True`, 열람 없으면 False, 정책·공개 오류.
3. `web/src/bank/RootLearning.tsx`: `showMap()` 분기, `mapRequested` 제거, `RootMap summary` 폴백.

## 검사 명령과 성공 조건
- `server/`: `<venv python> -m tests root_` 전부 통과(새 `root_lecture_map` 포함).
- `web/`: `npm run build`(tsc 포함) 통과.
- 브라우저: 격리 fixture API(`tests.serve_root_fixture`) + vite로 회차 없는 상태에서 「개념 지도」 → 지도 표시, 충돌 배너 없음.

## 위험·복원·승인할 범위
- 위험: 지도를 본 날 새 회차가 `mapSeen`으로 시작해 그날 회상이 도움받음으로 기록된다(기존 정책의 연장).
- 복원: `git revert`. 추가된 `map_view` 행은 집계에 쓰이지 않아 남아도 무해.
