# 감염과 면역 이동 12강의 run ID를 현재 시간표 번호로 — Spec

## R1. 운영 DB: 한 트랜잭션에서 쌍 맞바꾸기

- 강의를 가리키는 키는 모든 표에서 글자 쌍 `(subject, run_id)`다. FK에는 ON UPDATE CASCADE가 없다.
- 그래서 쌍마다 임시 키를 거쳐 세 번에 옮긴다(A→임시, B→A, 임시→B). 자식 행을 먼저 옮기고 lecture 행을 마지막에 옮긴다.
- 대상은 `subject`와 `run_id` 열이 함께 있는 모든 표다. 표 목록을 하드코딩하지 않고 reflect로 찾는다.
  - FK 표: asset, run_meta, lecture_waive, quiz_bank, bank_*, prequiz_job, note_read, lecture_memo, preview, user_preview, user_review, pre/main_item, card_edit, quiz_publication_check
  - FK 없는 표: asset_grab, preview_open, attempt, review_log, *_archive, root_*, connection_*
- 번호가 키 노릇을 하는 문자열도 바꾼다.
  - lecture `uid`(번호#주제#교수)
  - `study_hidden_lecture.lecture_key`(과목/번호)
  - `asset.object_key`(R2 복사 뒤, R2 절)
- **하지 않는 것**: 이미 만든 것을 설명하는 기록은 그대로 둔다. 그 기록이 가리키는 파일과 판이 옛 번호로 만들어졌기 때문이다.
  - run_meta `payload`(덱 이름)
  - root_content `document.review.lecture_id`. 새 판 등록 때만 대조한다.
  - root_generation `packet.runId`·`inputHash`
  - `preview_source._previousAttachments`. 옛 R2 객체를 지우지 않으므로 그대로 열린다.
  - 진행 중인 생성 요청(prequiz_job·root_generation)이 있으면 멈춘다. 끝난 요청만 옮기고, 끝난 요청은 이어 하기 대상이 아니다.
- **미코·무산소 쌍은 행 단위가 아니라 내용 단위로 옮긴다.**
  - asset은 파일 이름과 족보 교수로, pre_item·preview는 문항 내용으로, run_meta·덱은 덱 이름으로 주제를 판정한다.
  - 학생 기록(attempt·review_log·user_preview·preview_open·user_review)은 그 기록이 가리키는 문항·덱을 따라간다.
  - 판정이 애매한 행이 하나라도 있으면 적용하지 않고 목록을 보여준다.
  - 두 행에 같은 이름·같은 크기의 슬라이드 그림(첫 덱과 11-08에 다시 만든 덱)이 있다. 옮겨 오는 쪽의 asset 행만 지우고 R2 객체와 영수증 사본을 남긴다.
  - 크기가 다르거나, 노트·족보·덱처럼 강의당 하나인 종류가 겹치면 멈춘다.
- **두 번 돌지 않게 한다**: 각 강의 행이 아직 맞바뀐 칸(옛 번호)에 연결되어 있을 때만 계획을 만든다. 이미 옮긴 DB에서는 멈춘다.
  - 적용은 검토한 계획의 지문(`--expect-plan`)과 같을 때만 한다.
- **멈추는 조건**: 표의 행 수·지문이 검토한 사전값과 다를 때, 진행 중인 prequiz_job·root_generation이 있을 때, 옮긴 뒤 키가 겹칠 때. 이때 commit하지 않는다.
- 사전·사후 스냅샷과 영수증을 남긴다. 영수증으로 되돌리기가 된다.

## R2. R2 자료: 새 경로로 복사하고 키를 바꾼다

- `asset.object_key`는 `lectures/<과목>/<번호>/<종류>/<파일>`이다.
  - 그대로 두면 읽기는 된다.
  - 문제는 다시 올릴 때다. 새 번호로 키를 만들면 맞바꾼 상대 강의의 기존 키와 겹친다. 그러면 상대 파일을 덮거나 상대 asset 행을 집는다.
- 그래서 134개 객체를 새 번호 경로로 **복사**하고 `object_key`를 바꾼다.
  - 옛 객체는 지우지 않는다(되돌리기용).
  - 복사는 DB 트랜잭션 전에 하고, 해시가 같은지 확인한다.
  - `preview_source._previousAttachments[].objectKey`도 같이 바꾼다.

## R3. 러너·로컬

- **적용 순서**: 진행 중인 아데노 Main-Quiz가 끝난 뒤 러너를 끄고 적용한다. 다시 켜기 전에 아래를 맞춘다.
- `data/timetable/identities/2026-2.json`과 `2026-2-notes.json`
  - 12강의를 지운다. 번호가 시간표와 같아지므로 별칭이 필요 없다.
  - `runner/filenames.py`·`runner/ahead.py`는 파일이 비어도 동작하게 한다.
- `runs/` 안의 것
  - `runs/<번호>/` 폴더와 `agent.<번호>.log`
  - 예습 run 폴더(`runs/2511xx_xx`)의 pre_target.json `run_id`·deck_name
  - `_pairs/감염과 면역.json`의 올해 번호 키, `published.json`·`prequeue.json`
  - 러너의 로컬 SQLite 사본
- 사람이 만든 파일(HOLD·CHOSEN·preview.md·note.md 등)은 내용을 바꾸지 않고 자리만 옮긴다.
- 옮기기 전에 사본을 남긴다.

## R4. 이미 나간 덱·브라우저

- 학생이 받은 예습 .apkg는 다시 만들지 않는다.
  - 카드 guid가 작년 번호로 정해져 있어 다시 만들면 Anki에 이름만 바뀐 중복 덱이 생긴다.
  - R2의 파일 이름에 옛 번호가 남아도 된다.
- 다음에 새로 만드는 덱부터 새 번호 이름을 쓴다.
- 브라우저 북마크 `/lectures/감염과 면역/<옛 번호>`는 맞바꾼 상대 강의를 연다. 막지 않고 release에 적는다.
- 아데노 Main-Quiz가 끝나 공개된 뒤 학생이 남긴 대기 쓰기가 있을 수 있다. 적용 직전에 root_session·root_event 수를 보고, 있으면 그 행도 같이 옮긴다.

## R5. 검사

- 격리한 로컬 DB에서 운영과 같은 모양의 데이터로 왕복 검사한다(적용 → 되돌리기 → 바이트 같음).
- 섞인 쌍 판정표를 사람이 본다.
- 적용 뒤 확인
  - 12강의마다 제목·시간표 칸·자료·문항 수·학습 기록 수가 주제를 따라 옮겨졌는지
  - 다른 강의 314개의 지문이 같은지
  - 화면에서 11-10 10:00 칸이 `261110_02` 아데노로 열리는지
