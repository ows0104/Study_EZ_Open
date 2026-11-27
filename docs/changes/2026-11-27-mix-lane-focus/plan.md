# 모아풀기 강의별 중요도·저장값 기본 — 구현 계획

## 변경 범위·대상 파일·순서

1. `server/app/root_learning/content.py`: `saved_focus` 추가.
2. `server/app/routes/root_learning.py`: `mix_overview` 응답에 `focus` 한 칸. 다른 구역은 안 건드린다.
3. `web/src/types/rootLearning.ts`: `RootMixInfo.focus`.
4. `web/src/bank/RootBatch.tsx`: 시작 화면 중요도 처음 값(`savedOf`)·강의별 칩 펼침 기본.
5. 검사: `server/tests/test_root_mix.py`(고른 적 없음 → null, 강의 화면 저장 → 그 값, 마지막 선택), `web/tests/root-batch.test.cjs`
   (펼침 기본 반영, 저장값 기본·화면에서 바꿔도 저장값 그대로 새 검사).

## 검사 명령과 성공 조건

- server: `server/`에서 `PYTHONPATH=.. <메인 체크아웃 server/.venv>/python.exe -m tests root_mix`, `route_contract` (격리된 로컬 테스트 DB).
- web: `scripts/check_root_learning.py --check web-types`, `--check root-batch`(합성 고정물 서버, 운영 DB 미사용).

## 위험·복원·승인할 범위

- 위험: 강의 화면에서 좁혀 둔 강의는 모아풀기에서도 그 범위로 시작해 예전보다 문항 수가 적게 보일 수 있다(요청한 동작).
- 위험: 처음 값이 바뀌어 배포 전에 연 모아풀기 회차와 조건이 달라지면 「재개」 대신 새 회차 자리로 보인다. 같은 칩으로 맞추면 잇는다.
- 복원: `git revert`. 데이터 변경 없음.
- 승인할 범위: 위 파일의 로컬 구현·검사, PR. DB 스키마·운영 데이터·문항 변경 없음.
