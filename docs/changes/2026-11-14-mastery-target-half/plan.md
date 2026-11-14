# 구현 계획

승인: 사용자 요청(2026-11-14) 자체가 이 범위의 구현 지시. master 병합(=자동 배포)은 별도 승인.

## 파일

1. `server/app/root_learning/score.py`: `DISPLAY_TARGET_SCALE = 0.5`, `_unit_score`의 분모에 곱한다.
2. `server/tests/test_root_score.py`: 절반이면 100%, 4분의 1이면 50%, 1에서 자름.
3. `web/src/notices/GuidePage.tsx`, `web/src/lecture/LectureMastery.tsx`: 설명 문구.

## 위험·복원

- 병합 즉시 모든 사용자의 표시 학습률이 오른다(대략 두 배, 100에서 자름). 시험 계획의 하루 확보량도 그만큼 줄어든다.
- 복원은 상수를 1.0으로 되돌리거나 `git revert`.
