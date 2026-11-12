# Main-Quiz 공개 판 중복 재판정·선지 병렬 — 설계

## 요구사항과 수용 기준

R1 요청(서버 `server/app/routes/root_generation.py`): `RequestIn.duplicatesOnly`(기본 False). `restart` + `replacePublished` +
`pipeline == map-tree/3`일 때만 받고, 아니면 422. packet에 `duplicatesOnly: true`(입력 지문에 포함). 플래그 없는 요청의 packet은 지금과 같다.

R2 러너(`runner/connection_generation.py`): packet에 `duplicatesOnly`가 있으면
- `runs/_root-generation/<restartOf>/`가 이 PC에서 게시된 실행이어야 한다(`published.json` ready, 판이 `generation/result.json`과 같음).
- 그 실행의 `front/derived-packet.json`의 Map·포인트·앞 단계 증거·문제은행으로 이 요청의 생성 packet을 다시 만든다(`map_tree.derive_packet`).
  앞 단계는 돌지 않는다.
- 생성기를 `--duplicates-of <이전 generation 폴더>`로 부른다.
- 게시 뒤 이전 판의 근거(`evidence/evidence.json`)를 판 이름만 바꿔 올린다. 없으면 지금처럼 새로 만든다.

R3 생성기(`quizbank/connection_dedupe.py`, `connection_generate --duplicates-of`): duplicates-only/1.
- 이전 결과를 이전 packet으로 검증하고, 강의 입력(요청 식별 필드·원본 사본 위치를 뺀 packet)이 같아야 한다. 판 이름은 달라야 한다.
- 이전 폴더의 단계 영수증을 새 폴더에 하드 링크(실패하면 복사)하고 ledger를 이 packet의 입력 지문·실행 지문으로 바꿔 둔다
  (`ledger.duplicatesOnly`에 이전 판·지문). 이전 단계는 다시 돌지 않는다.
- 근거 문항이 둘 이상인 목표만 `v4-coverage-dup-<k>`(목표 COVERAGE_CHUNK개씩, 병렬)로 현재 커버 지시문에 다시 묻는다.
  입력 문항은 그 목표들의 근거 문항(은행 순서).
- 판정에서 `duplicates` 묶음만 가져온다(`_merge_row(..., by_evidence=True)`와 `_first_evidence`, goal-duplicates/1과 같은 규칙).
  근거·상태·이유는 이전 판정 그대로.
- 평가·감사·문서를 새 판 이름으로 다시 조립한다. 문항·검토·중요도·의학 검토·맥락은 이전 결과의 것.
- manifest는 이전 것에 바뀐 값(입력 지문, 실행 지문, 단계, 커버, 평가, readiness, notReady, 합친 중복, 파생 packet)과
  `duplicatesOnly`(이전 판·판정한 목표·바뀐 묶음·과제 수 전후)를 더한다.

R4 선지(`quizbank/root_choices.py`, `runner/root_choices.py`):
- 묶음(작성 → 그 묶음의 의학 검토)이 `WORKERS = 3`개씩 함께 돈다. 문항·건너뜀·검토 기록·사용량은 묶음 순서로 모은다.
- 명령은 `--run-id`를 여러 번, 또는 `--all-published --subject <과목>`(이 PC가 게시한 그 과목 강의 전부)을 받고 `--workers`(기본 2)개
  강의를 함께 돌린다. 한 강의의 실패는 다른 강의를 막지 않고 종료 코드 1로 알린다.

수용 기준:
- A1 합성 /4 옛 ledger 실행(Q003·Q004 둘 다 D2 과제)에 duplicates-only를 돌리면 호출은 `v4-coverage-dup-0` 하나, 과제 4→3,
  `mergedDuplicates` Q004→Q003, 근거·상태·이유·문항·의학 검토는 그대로, 새 결과가 `automation.validate_result`를 통과한다.
- A2 같은 폴더에서 다시 돌리면 모델을 부르지 않고 같은 결과.
- A3 강의 입력이 다르거나 판 이름이 같으면 거절.
- A4 실제 5편(이 PC의 게시 결과)에 이전 판정을 그대로 돌려주는 가짜 판정으로 돌리면 과제·커버 행이 이전과 같고 검증을 통과한다(모델 없음).
- A5 서버: 플래그만, restart만, map-tree/2에서는 422. restart + replacePublished + duplicatesOnly는 packet에 표시가 남고 공개 판은 새 판 게시 전까지 그대로.
- A6 러너: 이전 실행을 찾아 생성기에 넘기고 근거를 판 이름만 바꿔 올린다. 이 PC에서 게시하지 않은 실행은 거절. 플래그 없는 요청은 지금과 같다.
- A7 선지: 세 묶음의 작성 호출이 동시에 떠 있어야 끝나는 검사가 통과하고, 결과 순서는 묶음 순서다. 여러 강의도 함께 돈다.

## 책임·입출력 계약·오류 상태
- 서버는 플래그를 packet에 남기는 것뿐이다. 결과 검증·게시(`put_result`)·공개 판 교체 규칙(#123)은 그대로.
- 생성기는 하위 프로세스(기존 경계). 실패는 「연결 자동출제 보류: …」로 끝나고 러너는 지금처럼 실패를 보고한다. 같은 요청의 이어 하기는
  `--resume <이유>`를 생성기에 넘긴다.
- 결과 형식·manifest 필수 키·서버 검증·DB 스키마 변경 없음(`duplicatesOnly`는 manifest의 선택 항목).

## 호환성과 데이터 보존
- 이전 실행 폴더·판·학습 기록·DB 행은 바뀌지 않는다. 영수증은 하드 링크로 공유하지만 쓰기는 모두 새 파일로 바꿔치기(`g.write`)라 이전 파일을 고치지 않는다.
- 새 판이 게시되면 학생은 새 판을 본다. 기존 학습 기록은 옛 판에 남고 넘어가지 않는다(사용자 확인 2026-11-12).
- 선지 asset은 판에 묶인다. 중복 재판정으로 판이 바뀐 5편은 새 판이 올라간 뒤 선지를 만든다.
- 플래그 없는 요청·러너 경로·선지 결과 형식은 지금과 같다.
