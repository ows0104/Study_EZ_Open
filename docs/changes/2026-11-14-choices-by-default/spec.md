# Main-Quiz 선지를 게시 직후 기본 실행 — 설계

## 요구사항과 수용 기준
- `runner/connection_generation._generate`: `PUT …/result`가 `ready`를 돌려주고 `published.json`을 쓴 뒤,
  근거 보강(새로 만들기 또는 중복 재판정의 재사용)을 마치고 `root_choices.publish(client, subject, run_id, out, payload, model, run_forwarded)`를 부른다.
  - 출력은 `runs/_root-generation/<gid>/choices/` — 수동 명령과 같은 자리다.
  - 반환값과 예외는 게시 결과에 영향을 주지 않는다(`publish`가 모든 예외를 로그로 바꾼다). `_generate`는 그대로 0을 돌려준다.
  - 근거 보강이 먼저다. 기존 순서·근거 재사용 분기는 그대로다.
- `root_choices.publish`: 업로드가 끝나면 `choices/uploaded.json`에 `{revision, uploadedAt}`을 쓴다.
- `python -m runner.root_choices … --missing`: 강의마다 `uploaded(folder, revision)`이 참이면 모델을 부르지 않고 건너뛴다.
  - 표시가 있으면 표시의 revision만 본다.
  - 표시가 없으면 `choices/<revision>.json`이 2026-11-14 00:00 KST 이전에 만들어진 경우만 올린 것으로 본다(2026-11-12 일괄 업로드분).
    그 뒤 `--no-upload`로만 만든 파일은 올린 것으로 보지 않는다.
  - 끝 줄: `선지 작성 끝: 성공 n · 실패 m (…) · 이미 있음 k`. 건너뜀은 실패가 아니다(종료 코드 0).

## 책임·입출력 계약·오류 상태
- 생성기(`quizbank.root_choices`)와 asset 계약(`root_choices/<revision>.json`, `root-choices/1`)은 그대로다.
- 생성기 실패·업로드 실패 → 로그 「선지 작성 실패」, 게시는 성공. 서버는 선지 없이 지금처럼 보여 준다.
- 모델 호출: 강의당 작성·의학 검토 각 묶음 수만큼(40문항 묶음, 강의당 보통 3+3회). 기계 전체 Codex 한도(8)를 출제와 나눠 쓴다.

## 호환성과 데이터 보존
- 문항·판·검수 상한·학습 기록·서버 데이터는 읽기만 한다. DB 변경 없음.
- 2026-11-12에 올린 선지 asset은 건드리지 않는다(`--missing`이 건너뛴다).
- 판 게시가 끝난 뒤의 단계라, 선지 작성이 오래 걸리면 그 일감의 러너 종료가 그만큼 늦어진다(게시는 이미 끝남).
