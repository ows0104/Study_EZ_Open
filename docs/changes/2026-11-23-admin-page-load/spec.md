# 관리 페이지 로딩 속도 — 설계

## 요구사항과 수용 기준

1. `/admin`이 뜰 때 보내는 요청은 `overview`, `prequiz-jobs`, `users`, 숫자 전용 두 개다.
   `GET /api/admin/card-review`와 `GET /api/admin/bank-feedback`은 그 탭을 처음 열 때 나간다.
2. 탭 이름 옆 숫자(카드 검토·Quiz Bank 신고)는 화면이 뜰 때부터 선다. 목록을 읽은 뒤에는 목록의 수를 쓴다.
3. 신고 목록은 Main-Quiz 원본 문서(`root_content.document`)를 읽지 않는다. 사본 칸이 빈 행만 예외다.
4. 숫자 전용 경로는 목록 경로와 같은 수를 준다.

## 책임·입출력 계약·오류 상태

새 경로 둘(관리자만, 학생은 403):

- `GET /api/admin/bank-feedback/count` → `{"open": n, "done": m}`.
  `category != "good"`인 신고를 (과목, 편, 문항)으로 묶어, 열린 신고가 하나라도 있으면 open, 아니면 done.
  목록 경로의 `open`·`done`과 같은 함수(`_tally`)로 센다.
- `GET /api/admin/card-review/count` → `{"open": n, "done": m}`.
  run-meta가 걸어 둔 카드 중 판정이 있으면 done, 판정이 없고 문항이 올라와 있으면 open.
  목록 경로와 같은 줄(`_flagged_runs`)에서 시작하고, 문항 id·판정 키만 읽는다(갈래당 질의 하나).

바뀌는 기존 경로:

- `GET /api/admin/bank-feedback`: Main-Quiz 신고의 `question`을 그림 뺀 사본에서 만든다.
  지금 공개 판은 학습률 계산이 쓰는 사본 캐시(`light.revision_row`)를, 옛 판은 `root_content.light` 칸을
  읽는다. 사본 칸이 NULL인 행만 원본을 읽는다.
  응답 모양은 그대로이고, `question.stimuli[].png_base64`만 빠진다. 신고 탭은 문면·선지·답만 그리고
  그림을 그린 적이 없다.
- `GET /api/admin/card-review`: 응답 변화 없음(걸린 편을 고르는 부분만 함수로 뺐다).

화면:

- `AdminPage`는 뜰 때 숫자 전용 두 경로를 읽는다. 실패하면 숫자가 안 설 뿐 화면은 뜬다(기존 목록 실패와 같다).
- `CardReviewTab`·`BankReportTab`은 목록이 아직 없으면 `onChanged`(목록 읽기)를 한 번 부른다.
  읽은 목록은 `AdminPage`에 남아 다른 탭에 다녀와도 다시 읽지 않는다(기존과 같다).

## 호환성과 데이터 보존

- DB·스키마·저장 데이터 변경 없음. 읽기 경로만 바뀐다.
- 기존 두 목록 경로의 주소·응답 키는 그대로라 옛 화면(캐시된 번들)도 그대로 돈다.
- 새 화면은 새 경로 둘이 있어야 숫자가 선다. master 병합은 API를 먼저, 웹을 나중에 배포한다.
- 사본 캐시는 공개 판 것만 쓴다. 옛 판을 캐시에 넣지 않으므로 학습률 계산의 캐시를 밀어내지 않는다.
