# Main-Quiz 복습 간격 2차 — 구현 계획

승인: 사용자 「늦게 맞힌 보너스랑 난이도도 넣어서 만들어줘」(2026-11-18). master 병합(=자동 배포)은 별도 확인.

## 변경 범위·대상 파일·순서

1. `server/app/root_learning/policy.py`: `TARGET_RATING_POLICY` /4, `CURVE`, `curve_parameters()`, `curve_schedule()`,
   `effective_due`가 `examPressure` False면 압축하지 않음.
2. `server/app/root_learning/state.py`: `_rate`가 `target_due` 대신 `curve_schedule`(등급은 「내 중요도」, 없으면 문항 등급, 없으면 Core).
3. `server/app/routes/root_learning.py`: 평가 저장에 `curveParameters=policy.curve_parameters()`.
4. 검사: `server/tests/test_root_review_curve.py`를 spec 표·난이도·보너스·같은 날·시험 등급으로. 깨지는 기존 검사는 의도한 변화만 고친다.

## 검사 명령과 성공 조건

- `server/`에서 메인 체크아웃 venv, `PYTHONPATH=..`, `-m tests` 전체. master에서 통과하던 검사가 모두 통과.

## 위험·복원·승인할 범위

- 병합 즉시 모든 사용자의 지난 평가 복습일이 다시 계산된다. Again·Hard가 많은 Optional·Important 문항은 오늘 목록에서 빠지고,
  Essential은 지금처럼 자주 나온다.
- 복원: `git revert`로 /2·/3 평가는 1차 규칙으로 돌아간다. 병합 뒤 저장된 /4 평가는 `curveParameters`를 들고 있어 되돌린 코드는
  그 키를 무시하고 1차 규칙(target_due)으로 읽는다.
- 운영 DB 쓰기·스키마 변경 없음.
