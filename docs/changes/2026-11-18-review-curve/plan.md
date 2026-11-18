# Main-Quiz 복습 간격: 쉬운 문항이 곡선대로 빠지게 — 구현 계획

승인: 사용자 요청(2026-11-18) 「둘 다 적용하자」가 이 범위의 구현 지시. master 병합(=자동 배포)은 별도 확인.

## 변경 범위·대상 파일·순서

1. `server/app/root_learning/policy.py`
   - `TARGET_RATING_POLICY = 'roots-four-rating/3'`, `ROOT_MASTERY = {'firstFromRating': True, 'ratingAlpha': {...}}`.
   - `target_parameters()`에 `ROOT_MASTERY`를 더한다.
   - `next_mastery()`: 처음 평가면 평가 값, 아니면 `ratingAlpha.get(rating, alpha)`.
   - `transition()`: 도움 강등은 `self_rating is None`일 때만.
   - `replay_parameters()`: /2 사건에 `ROOT_MASTERY`를 더해 돌려준다. `state._rate`가 이것을 쓴다(R3).
2. 검사: `server/tests/test_main_quiz_four_ratings.py`(도움 받은 Good → independent, /3 저장), 새 `server/tests/test_root_review_curve.py`
   (spec 표의 출제일, /2 사건을 /3 규칙으로 읽기, 처음 Again 뒤 Good). `state.py`의 `_rate`가 `replay_parameters`를 쓴다.

## 검사 명령과 성공 조건

- `server/.venv` 파이썬, `PYTHONPATH=..`로 worktree의 계약을 읽게 하고, 격리된 sqlite로 root 관련 검사 전체를 돌린다.
- 지금 master에서 통과하던 검사가 모두 통과한다.

## 위험·복원·승인할 범위

- 병합 즉시 모든 사용자의 지난·새 평가가 새 곡선으로 읽혀 오늘 복습 수가 줄고 학습률이 오른다(R3).
- 복원: `git revert`로 지난 /2 사건은 예전 읽기로 돌아간다. 병합 뒤 저장된 /3 사건은 자기 파라미터로 재생되므로
  그 간격은 남는다(완전히 되돌리려면 `next_mastery`가 /3 키를 무시하게 해야 한다).
- 운영 DB 쓰기·스키마 변경 없음.
