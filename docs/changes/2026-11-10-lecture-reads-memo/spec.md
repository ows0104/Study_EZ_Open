# 강의록 회독 기록과 강의별 짧은 메모 — 설계

## 요구사항과 수용 기준
- 승인된 로그인 사용자만 쓴다(미로그인 401, 미승인 403, 없는 강의 404).
- 회독 추가는 한 줄을 더하고 새 개수를 돌려준다. 강의당 30회 상한(409).
- 회독 지우기는 그 사람의 가장 최근 한 줄만 지운다. 되돌리기는 웹이 다시 추가한다(시각은 새로 찍힌다).
- 메모는 300자 이하(초과 422). 끝 공백을 지우고 저장하고, 비우면 줄을 지운다.
- 강의 상세·시간표 응답에는 본인 값만 싣는다. 다른 계정 값은 0/빈 문자열이다.

## 책임·입출력 계약·오류 상태
- `POST /api/lectures/{subject}/{run_id}/note-reads` → `{"noteReads": n}`
- `DELETE /api/lectures/{subject}/{run_id}/note-reads/last` → `{"noteReads": n}`(지울 것이 없으면 0)
- `PUT /api/lectures/{subject}/{run_id}/my-memo` `{"memo": str}` → `{"memo": str}`
- `GET /api/lectures/{subject}/{run_id}`에 `noteReads: int`, `myMemo: str` 추가.
- `GET /api/timetable`의 강의마다 `noteReads: int`(`include_study=false`면 0).
- 경로는 개편 spec 초안의 `/api/me/note-reads` 대신 강의 경로 아래에 둔다 — 기존 `my-preview`·`my-review`와 같은 꼴이고 본문에 강의 키를 싣지 않아도 된다.
- 이용현황: `note_read`(남아 있는 회독 수, 회), `lecture_memo`(메모가 있는 강의, 마지막 저장 시각 기준) — 새 묶음 「회독·메모」.

## 호환성과 데이터 보존
- 새 표 `note_read`(id, user_id, subject, run_id, created_at; 색인 user_id+subject+run_id),
  `lecture_memo`(user_id+subject+run_id PK, body, updated_at). 둘 다 `lecture`에 FK(ON DELETE CASCADE, 기존 user_review와 같음), postgres RLS 켬.
- 기존 표·칼럼·학습 기록은 바꾸지 않는다. 회독은 학습률·SRS에 쓰지 않는다.
- 웹은 새 필드가 없으면 0/빈칸으로 그린다.
