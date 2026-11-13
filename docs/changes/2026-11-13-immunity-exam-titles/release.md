# 감염과 면역 1·2차 시험 칸 이름 — 배포 준비

## 코드 리뷰·검증 결과
- 시간표 JSON: `official-0bc9f61dc21c`·`official-6d947f1ae39d`의 title만 다름(파싱 비교). before 해시 = 11-05 after 해시.
- `server -m tests immunity`(11-05·11-11·이번 3개), `-m tests study_plan`, `pytest tests/runner -k "timetable or block"`(93) 통과.
- 새 테스트: 이름 전 계획 없음 → 적용 후 「감염과 면역 1차 시험」「감염과 면역 2차 시험」 계획(강의 > 0), 12/11은 그대로,
  반복 적용 무해, 현재 JSON 재seed와 같은 값, 되돌리기, 예상 밖 제목이면 중단.

## 배포 대상 버전·순서·데이터 변경
앱 코드 배포는 없다(서버·웹 동작 코드 변경 없음). 데이터만:
1. PR을 master에 병합.
2. 운영 `server/.env`를 가진 사람이 저장소 루트에서
   `python scripts/immunity_exam_titles.py --database production` — 두 행이 `"from": "시험"`, `"changed": true`인지 확인.
3. deploy 승인 기록 뒤 같은 명령에 `--apply`. 바뀌는 것: 두 행의 title·course·course_key.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 로그인 후 캘린더 머리 「오늘 복습」에 %p가 보이고, `/api/study-plan`의 `plans[0].title`이 「감염과 면역 1차 시험」.
- 롤백: `python scripts/immunity_exam_titles.py --database production --apply --reverse`.
- 운영 DB 쓰기(2·3단계)는 사용자 별도 승인이 필요하다.
