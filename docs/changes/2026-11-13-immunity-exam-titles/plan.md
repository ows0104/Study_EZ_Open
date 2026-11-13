# 감염과 면역 1·2차 시험 칸 이름 — 구현 계획

## 변경 범위·대상 파일·순서
1. `data/timetable/2026_본1_2학기_시간표.json`: 두 칸 title 변경.
2. `docs/changes/2026-11-13-immunity-exam-titles/source.json`: before/after 파일 해시와 두 칸 before/after.
3. `scripts/immunity_exam_titles.py`: 조건부 운영 반영(기본 검사, `--apply`, `--reverse`).
4. `scripts/immunity_timetable_update.py`: 시간표 해시 검사가 이 변경의 after 해시도 받도록(두 칸 외 동일 확인 포함).
5. 테스트: `server/tests/test_immunity_exam_titles.py` — 격리 SQLite에 seed 후 도구 적용·반복·되돌리기, `build_study_plan` 결과.

## 검사 명령과 성공 조건
- `server/.venv/Scripts/python.exe -m tests immunity` (기존 11-05·11-11 테스트 + 새 테스트) 통과.
- `python -m pytest tests/runner/test_timetable_identity.py -q` 통과.
- 격리 DB에서 `build_study_plan` 첫 계획이 「감염과 면역 1차 시험」, 강의 수 > 0.

## 위험·복원·승인할 범위
- 운영 DB 쓰기는 별도 승인. 이 저장소 어디에도 운영 `DATABASE_URL`이 없어, `server/.env`를 가진 사람이
  `python scripts/immunity_exam_titles.py --database production` (검사) → `--apply` 순서로 실행한다.
- 복원: `--reverse`(두 행 title·course·course_key를 「시험」으로).
