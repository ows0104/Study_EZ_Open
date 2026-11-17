# Main-Quiz 개인 수정 형식 — 설계

## 저장
`bank_personal_edit.structure JSON NULL`. NULL = 원래 형식(기존 행·기존 Quiz Bank 수정 모두 NULL, 동작 그대로).
값: `{format, mcq_mode, answer_units, options, correct_option_ids, explanation}`. 형식이 원래와 다를 때만 저장한다.
`cli.py` `ADDED_COLUMNS`에 한 줄 — 운영 DB는 API 배포 전에 `init-db`로 붙인다.

## 적용 (`bank_personal.apply_edit`)
structure가 있으면 발문·정답과 함께 그 형식·구조·해설로 바꾸고 `personalAnswer`는 끈다(구조와 해설을 사용자가 함께 정했으므로
판 문항처럼 보인다). 빈칸은 `answer_units`를 발문의 `{…}`에서 뽑는다. structure가 없으면 지금 규칙 그대로.

## API (`/api/root-learning/.../questions/{id}/personal`)
- GET: original·draft에 `format`, `explanation`, `options`, `correctOptionIds`, `mcqMode`. 수정 가능하면 `formats`(여섯).
- PUT: `structure`(선택) — `format`, `mcq_mode`, `options`, `correct_option_ids`, `explanation`.
  형식별 조건(위)은 422로 알린다. 나열의 채점 항목은 정답 줄, 객관식 정답 글은 고른 보기 글로 서버가 채운다.
  원래와 같은 형식이면 structure를 버리고 지금처럼 글만 저장. 제보 correction에 `proposed.format`, changedFields `format`.

## 선지
형식이 바뀐 수정본에는 덧붙인 선지(객관식 모드·V)를 붙이지 않는다(`mcq._resolve`). 원래 형식의 칸이라 맞지 않는다.
객관식으로 바꾼 문항은 사용자가 적은 보기가 그 문항의 선지다.

## 웹 (`PersonalQuestionDialog.tsx`)
`formats`가 있으면 「문항 형식」 선택. 원래 형식이면 지금 화면. 다른 형식이면 형식별 칸(정답·나열 줄·O/X·보기와 정답·학습 유형)과 해설.
빈칸에서 다른 형식으로 바꾸면 발문의 `{…}` 괄호만 벗긴다.

## 호환성과 데이터 보존
기존 개인 수정본·학습 기록·판 문항·fingerprint는 바뀌지 않는다. 기존 Quiz Bank 경로는 structure를 보내지 않는다.
