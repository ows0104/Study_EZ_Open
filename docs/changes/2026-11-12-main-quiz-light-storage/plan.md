# Main-Quiz 저장 방식: 그림 뺀 사본 칸·그림 표 — 구현 계획

## 변경 범위·대상 파일·순서
1. `server/app/models/root_learning.py`, `models/__init__.py` — `light` 칸, `RootImage`, `before_insert`.
2. `server/app/root_learning/light.py` — `stored`·`from_stored`·`images_of`·`save_images`·`fill`·`revision_row`·`hydrate`, `_load`가 사본 칸 우선.
3. `server/app/routes/root_learning.py` — `active`·`main_quiz_entry`·`learner_front`·`snapshot_question`·`task_fingerprint`.
4. `server/app/cli.py` — `main-quiz-light` 명령, `ADDED_COLUMNS`.
5. 검사: `server/tests/test_root_light.py` 8번(아래), `test_root_personal.py`(원본을 고치는 시험이 사본도 같이 고치게).

## 검사 명령과 성공 조건
- `server/.venv/Scripts/python.exe -m tests` 전체. 알려진 환경 실패만 허용(`root_map_tree*`: venv에 pymupdf 없음).
- `test_root_light` 8번: 등록 때 사본·그림 채움(같은 그림 한 줄) / 풀이 시작·보기·미리 받기·답 보기·평가·개인 수정 열기·개요에서
  원본 읽기 0회 / 화면 그림·개인 수정 revision·평가 지문이 원본과 같음 / 요청 뒤 캐시 사본 변화 없음 /
  사본 칸·그림을 지운 행도 동작 / 채우기 보기만은 아무것도 안 바꾸고 `--apply`는 넣을 때와 같은 값으로 채움, 원본 그대로.
- 운영 읽기 전용 리허설(`SET TRANSACTION READ ONLY`): 34판 불일치 0.

## 위험·복원·승인할 범위
- 승인(사용자 「Both steps」, 운영 DB 쓰기 포함): 운영에서 `python -m app.cli main-quiz-light --apply` 한 번 —
  `root_image` 표 생성, `root_content.light` 칸 추가, 34판 채우기(약 +136 MB). 원본·학습 기록 변경 없음.
- 순서: ① 운영 `main-quiz-light`(보기만) → ② `--apply` → ③ 다시 보기만으로 0개 확인 → ④ PR 병합(자동 배포) → ⑤ 로그 관측.
- 복원: 코드 revert/이전 revision. 칸·표는 남겨도 옛 코드에 무해.
