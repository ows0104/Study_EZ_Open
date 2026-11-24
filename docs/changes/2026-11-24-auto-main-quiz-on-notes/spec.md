# 필기 업로드 시 Main-Quiz 자동 요청 · 러너 자동 시작 15초 — 설계

## 요구사항과 수용 기준
- R1 올해 필기(`notes_current`)가 **처음** 등록된 업로드 완료(`POST …/uploads/complete`)에서 서버가 Main-Quiz 요청을 넣는다.
  - 요청 본문은 「Main Quiz 만들기」 버튼과 같다: `inputMode: source`, `authoring: cli`, `pipeline: map-tree/3`, `privatePilot: false`.
  - 원본은 그 시점에 등록된 올해 필기(S1)와 족보(S2, 있으면)다. 같은 업로드에 실린 족보는 든다.
- R2 다음 강의는 요청하지 않는다. 업로드는 그대로 성공한다.
  - 실습·CBL·PBL(`auto_review_excluded`, 기존 자동 복습 규칙).
  - 공개된 판이 있는 강의(`root_control.revision`).
  - Main-Quiz 요청이 한 번이라도 있었던 강의(상태 무관). 필기를 바꿔 올려도 다시 요청하지 않는다.
  - 버튼 요청이 거절하는 경우(PDF가 아닌 원본, 열린 문제은행 작업, 원본을 못 읽음). 이유는 서버 로그에 남긴다.
- R3 같은 파일의 재확인(러너가 쓸기마다 보내는 `uploads/complete`)은 다시 요청하지 않는다.
- R4 자동 요청의 일감은 `origin: auto`, 요청자 빈칸, 단계 문구 「올해 필기가 올라왔다 — …」다.
  - 하루 자동 상한(`JOB_AUTO_DAILY_CAP`, 예습·Quiz Bank 자동 일감과 함께 셈)을 넘으면 요청은 남기고 일감을 `held`로 세운다.
  - 보류된 요청은 관리자가 강의 화면의 「이어 하기」(이유 필요)로 시작한다.
- R5 러너의 claim은 자동 일감도 버튼 일감처럼 자기 요청(`rootGenerationId`)에 묶는다. 러너는 버튼 요청과 같은 길로 출제·게시한다.
- R6 자동 요청의 소유자는 `runner`다. 관리자는 누구나 그 요청을 이어 하거나 새로 출제할 수 있다.
  - 새로 출제한 요청은 누른 관리자의 것이다. 다른 관리자의 요청에 대한 기존 거절은 그대로다.
- R7 러너 창의 자동 시작 대기 기본값은 15초다(`desktop_control.AutoStart`). 취소·한 번만 등록·일시정지 동작은 그대로다.

## 책임·입출력 계약·오류 상태
- `server/app/routes/admin.py` `complete_uploads`: 자료를 먼저 commit한 뒤 `_auto_main_job`을 부른다.
  자동 요청이 실패해 rollback해도 방금 올린 자료는 남는다. 응답의 `queued`는 선 일감(없으면 `null`)이다.
- `server/app/routes/root_generation.py`
  - `request`(버튼 endpoint)는 `submit`을 부른다. `submit(…, auto=<이유>)`가 자동 일감의 origin·요청자·상한을 정한다.
  - `auto_request`가 R2의 건너뛰기를 정하고, 예외를 삼켜 `None`을 돌려준다.
  - 요청 전에 세션을 DB 값으로 다시 읽는다(`expire_all`). 방금 만든 자산의 업로드 시각 표기가 DB가 돌려주는 값과 달라
    `input_digest`가 갈리면, 관리자가 같은 입력으로 이어 할 때 다른 요청으로 보인다.
- 러너 코드는 자동 요청을 위해 바뀌지 않는다(claim 응답의 `rootGenerationId`만 본다).

## 호환성과 데이터 보존
- DB 스키마 변경 없음. 기존 요청·공개판·학습 기록을 건드리지 않는다(R2).
- 버튼 요청의 동작·응답은 그대로다. 로컬에서 `root_generation.request(...)`를 직접 부르던 스크립트도 그대로 돈다.
- 구 러너(재설치 전)도 자동 일감을 처리한다. 15초는 러너 설치본을 새로 깔아야 반영된다.
- 배포 순서: 서버가 먼저 나가도 된다. 자동 요청은 배포 뒤 새로 올라오는 필기부터다.
