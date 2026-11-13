# 감염과 면역 1·2차 시험 칸 이름 — 설계

## 요구사항과 수용 기준
- 시간표 JSON과 운영 `timetable_event`의 두 행이 같은 title을 가진다. course·course_key는 `seed-timetable`과 같은 규칙
  (`course_from_title`, `normalize_stem`)으로 정한다.
- `build_study_plan`: 11/02~11/19 감염과 면역 강의 → 1차 시험, 11/23~11/26 → 2차 시험으로 묶인다.
- 웹 `studyBlocks.ts`: `studyBlockKey("감염과 면역 1차 시험")` = `감염과면역1차`로 1차 블록에, 2차 시험은 2차 블록에 정확히 붙는다
  (지금은 「시험」 키로 가까운 블록에 붙어 결과가 같다). `splitNames`의 1차 시험 판별(`1차`)도 그대로 맞는다.
- 머리 표시 「1차 시험」(CalendarPage `nextExam`)은 title+details에서 차수를 읽으므로 그대로다.
- 러너 `runner/blocks.py`는 로컬 SQLite를 보고, `base_name`이 「감염과 면역 1차」가 되어 지금(「」로 버려짐)처럼 블록 끝을 밀지 않는다. 동작 변화 없음.

## 책임·입출력 계약·오류 상태
- 데이터: `data/timetable/2026_본1_2학기_시간표.json` 두 칸의 `title`만.
- 운영 반영: `scripts/immunity_exam_titles.py` — 기본은 검사만, `--apply`일 때만 쓴다. 대상 두 행이
  원래 값(title 「시험」, 같은 date·details)이거나 이미 바뀐 값일 때만 진행하고, 다른 값이면 멈춘다.
  title·course·course_key 세 칸 외에는 쓰지 않는다. `--reverse`로 되돌린다.

## 호환성과 데이터 보존
- 강의·학습 기록·문항·링크는 건드리지 않는다. `lecture.timetable_event_id`는 강의 칸만 가리키므로 시험 칸 제목과 무관하다.
- 11-05 도구 `scripts/immunity_timetable_update.py`는 시간표 파일 전체 해시를 고정해 검사한다. 이번 변경 뒤 파일
  해시가 바뀌므로, 그 도구가 11-05 해시 또는 이 변경 폴더 `source.json`이 기록한 해시(두 칸 외 동일함을 이 변경이 검사)를 받게 한다.
