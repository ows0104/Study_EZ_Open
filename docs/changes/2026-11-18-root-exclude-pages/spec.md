# Main-Quiz 운영자 제외 쪽(page-withhold/1)과 261109_02 재출제 — 설계

## 요구사항과 수용 기준
- R1 기록: `runs/page-exclusions.json`
  `{"version": 1, "lectures": {"<과목>/<runId>": {"sources": [{"assetId", "sha256", "pages": [36, "37-48"]}], "reason", "approval", "at"}}}`.
  - 쪽은 1부터 세는 원본 PDF 쪽 번호다. 정수나 「a-b」 범위로 적는다.
  - 이유·승인 발언·시각이 없거나 형식이 틀리면 그 일감을 보류한다(`PageExclusionError`). `fill-goals.json`·`model-overrides.json`과 같은 태도다.
  - 키를 generationId가 아니라 강의로 둔 이유: generationId는 요청 뒤에야 생기고, 러너가 바로 집어 가면 기록이 늦는다.
    대신 자료를 자산 ID와 원본 SHA-256 둘 다로 가리킨다. 필기가 바뀌면 기록이 맞지 않아 보류되고, 조용히 다른 파일에 걸리지 않는다.
- R2 굳히기: 러너가 요청의 원본을 내려받은 직후(`connection_generation.run_generation`) 맞는 자료 옆에
  `<사본>.withheld-pages.json`(policy `page-withhold/1`, sourceSha256, pages, 이유·승인·시각, frozenAt)을 쓴다.
  - 한 번 굳힌 실행은 기록이 바뀌어도 처음 것을 쓴다(이어 하기 일관성).
  - 기록이 가리킨 자료가 요청에 없으면 보류한다. 쪽이 PDF 쪽 수를 넘으면 보류한다.
    이미 자료를 만든 실행(`front/material`·`generation/material` 있음)에 처음 걸려도 보류한다(앞 단계와 생성기가 다른 자료를 보지 않게).
- R3 가린 사본: 모델 입력을 만드는 세 곳이 `quizbank.withheld_pages.document(path)`로 원본을 연다.
  1. 앞 단계 `root_front.Front.prepare`: material의 PDF 사본·쪽 글·쪽 그림.
  2. 생성기 `connection_generate.prepare`: 쪽 글·쪽 그림. 앞 단계의 early normalize도 이 함수를 쓴다.
  3. 근거 보강 `evidence_sources.prepare`: 쪽 글·쪽 그림, 모델에게 주는 PDF 경로는 가린 사본(`model-source.pdf`).

  제외 쪽은 같은 크기의 빈 쪽으로 바뀐다. 거기에는 안내 한 줄만 있다:
  `[Page N withheld by the operator: … do not cite this page …]`.
  쪽 수와 번호는 원본 그대로다. 그 쪽을 가리키는 책갈피와 문서 메타데이터도 뺀다.
- R4 쪽 번호 보존: 원본 파일·packet의 `sha256`·`sizeBytes`·`localPath`는 그대로다.
  - 지문 검사(앞 단계·생성기·근거·그림 crop), 서버의 파생 packet 재계산(`validate_result`), 게시된 인용 쪽·근거 지면은 모두 원본 기준으로 맞는다.
  - 앞 단계 `input.json`의 그 자료 칸에 `withheld_pages`를 적는다.
  - 학생 화면의 그림·근거 crop은 지금처럼 원본에서 자른다. 모델이 제외 쪽을 고르지 않으므로 거기서 잘릴 쪽도 없다.
- R5 확인: 앞 단계 호스트 검사(`refs_ok`, 문제은행 그림 쪽)는 제외 쪽 인용을 거절한다. 기존 후속 1회로 저자 세션에 돌아간다.
  - 대조의 쪽 검토는 제외 쪽을 넣어도 빼도 통과한다.
  - 생성기 결과는 게시 직전에 제외 쪽 인용을 세어 `withheld-citations.json`에 남기고 로그로 경고한다. 막지 않는다.
- R6 기록 없음: 사이드카가 없는 자료는 지금과 바이트 단위로 같은 입력이다. 다른 강의·Quiz Bank 경로는 바뀌지 않는다.

## 책임·입출력 계약·오류 상태
- `quizbank/withheld_pages.py`: 사이드카 읽기(지문 확인)·가린 문서 열기·가린 사본 저장. runner를 import하지 않는다.
- `runner/page_exclusions.py`: 운영자 기록 읽기·검사, 실행에 굳히기, 결과의 제외 쪽 인용 세기.
- 오류: 기록 형식 오류, 자료 불일치, 쪽 범위 초과, 이미 시작한 실행이면 `PageExclusionError(ValueError)`로 요청을 보류한다.
  사이드카 지문이 사본과 다르면 `ValueError`가 나고 앞 단계·생성기가 모델 호출 전에 멈춘다.

## 호환성과 데이터 보존
- 서버·DB·웹·프롬프트·스키마·검수 상한은 바뀌지 않는다. 서버 packet의 inputHash도 그대로다.
- 원본 사본(`source-<i>.pdf`)은 건드리지 않는다. 사이드카는 옆에 새 파일로 남는다(삭제 없음).
- 이전 실행 폴더(`2bcdcf1f…`, `d4b5c7e6…`, `a2dee040…`)는 손대지 않는다.
