# Main-Quiz 저장 방식: 그림 뺀 사본 칸·그림 표 — 설계

## 요구사항과 수용 기준
- 모델 `RootContent`: `document`는 미뤄 읽기(deferred). `light JSON(none_as_null) NULL`(deferred) 추가.
  `RootImage(sha256 PK, png_base64, created_at)` 추가. `before_insert`가 `light.fill`을 부른다.
- `light.stored(doc)` = `{document: 그림 뺀 사본, task_fingerprints: 원본 지문}`. `light.fill`은 사본을 채우고 없는 그림만 넣는다
  (Postgres·SQLite 모두 ON CONFLICT DO NOTHING).
- 읽기: `light._load`는 `light` 칸을 읽고, NULL이면 원본에서 만든다(채우기 전 행). `light.revision_row`가 풀이·개요·입장의 판을 준다.
- `light.hydrate(db, doc, q)`: 문항 하나의 그림을 `root_image`에서 되붙인 새 dict. 표에 없으면 원본에서. 캐시·사본은 고치지 않는다.
- 라우트: `active`·`main_quiz_entry` → `revision_row`. `learner_front` → 띄우는 문항만 hydrate. `snapshot_question(db, …)` → hydrate
  (개인 수정 `bank_personal.revision`이 문항 전체를 해시하므로). `task_fingerprint` → 사본이 든 원본 지문.
- CLI `main-quiz-light`(기본은 보기만, `--apply`로 실행): `root_image` 표·`light` 칸만 만들고 NULL인 판을 판마다 한 트랜잭션으로 채운다.
  `ADDED_COLUMNS`에도 적어 init-db와 맞춘다.

## 책임·입출력 계약·오류 상태
- API 응답 모양 그대로(그림은 지금처럼 data URL).
- 사본 칸이 빈 판·그림이 표에 없는 문항: 원본에서 읽어 동작한다(느릴 뿐). 채우기는 몇 번을 돌려도 남은 것만.
- 관리자 경로(등록·공개 검증·신고함·판 목록)는 원본을 쓴다.

## 호환성과 데이터 보존
- 원본 `document`·digest·검토 표시·학습 기록·개인 수정·제보는 읽기만 한다. 기존 행에는 `light` 칸 값만 더한다.
- 배포 순서: 운영에 칸·표를 먼저 만들고(채우기 포함) 그다음 코드 병합. 옛 코드는 새 칸·표를 모르므로 먼저 만들어도 무해.
  거꾸로(코드 먼저)면 `root_content` 조회가 없는 칸 때문에 실패한다.
- 되돌리기: 코드 revert면 칸·표는 쓰이지 않고 남는다(지울 필요 없음).
