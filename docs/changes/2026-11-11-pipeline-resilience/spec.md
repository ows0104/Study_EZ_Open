# Main-Quiz 파이프라인 안정화·시간 단축 — 설계

## 요구사항과 수용 기준
R1 앞 단계 되돌려주기. 지도·포인트·문제은행·대조·보완·재대조의 결과가 호스트 검사에서 거절되면, 정확한 오류를
같은 세션에 한 번 보내 그 파일만 고치게 한다(형식·구조만. 판정·내용은 모델 것). 다시 거절되면 지금처럼 실패로 남긴다.
- 거절된 파일은 `refused-<파일>`, 오류는 `check-failure.json`, 후속 응답은 `model-response-followup.json`에 남는다.
- `state.json`은 두 호출의 사용량·시간 합과 `followup{error, refusedSha256}`을 갖는다. 파생 packet의 단계 행은 그대로다.
- 후속이 다른 세션이면 실패. 고정 입력 불변 검사는 후속 뒤에도 한다.

R2 문제은행 미리 검사. 앞 단계 문제은행 검사에 생성기 접수와 같은 함수(`intake_projection` → `validate_bank` →
`intake_rejections`)를 더한다. 문항에 속하지 않는 오류는 여기서 R1로 돌아간다. 문항 하나의 오류와
「충돌 인용 누락」은 접수에서처럼 통과한다(그 문항만 빠지고 기록됨).

R3 네트워크 끊김 1회 재실행(transport-retry/1). 단계 호출이 `codex.network_failure`인 오류로 끝나면
(CLI 세션 오류이고, 네트워크 표지가 있고, 시간 초과·콘텐츠 거절·사용량 한도가 아님) 모델 호스트 이름이 풀릴 때까지
기다린 뒤(15초 간격, 최대 15분) 같은 입력으로 한 번 다시 부른다.
- 한 단계에 한 번. 둘째 끊김, 15분 안에 돌아오지 않는 네트워크, 다른 모든 실패는 지금처럼 멈추고 관리자 재개를 기다린다.
- 생성 단계: 끊긴 호출의 진단은 `.native/<단계>.net/`, ledger `transportRetries[{policy, stage, error, kept}]`.
  결과 manifest에는 넣지 않는다(판정이 없었던 호출이고 manifest 키는 계약으로 고정).
- 앞 단계: 끊긴 호출이 남긴 파일은 `.net-<단계>/`, `state.json`의 `transportRetries`.
- 추가·수정 회차, 판정 기록, 재개 이력은 움직이지 않는다.

R4 앞 단계 동시 실행(map-tree/2 이상). 포인트 → 대조 → (보완 → 재대조)를 한 줄로 묶어 지도, 문제은행과 나란히 돌린다.
- 셋 중 하나가 실패해도 나머지는 끝까지 돌아 재개 때 다시 부르지 않는다. 오류는 지도·포인트 줄·문제은행 순으로 첫 것을 올린다.
- 재개 규칙 그대로: 포인트를 다시 돌리면 그 뒤 대조도 다시 돌고, 지도·문제은행의 재실행은 서로를 묵히지 않는다.
- map-tree/1(문제은행 없음)은 지금 순서 그대로.

R5 동시 실행 수. 한 실행의 동시 모델 호출 `BATCH_WORKERS` 3 → 6(`STUDYEZ_ROOT_WORKERS`, 1~12).
기계 전체는 `studyez_llm.execution.slot`이 8로 묶는다(`STUDYEZ_CODEX_SLOTS`). 자리가 없으면 실패하지 않고 기다리며,
기다림은 호출 제한 시간에 들지 않는다. 죽은 프로세스의 자리는 파일 잠금과 함께 돌아온다.

R6 추가 회차 커버 확인. `/4`의 `coverage-<n+1>-<k>` 조각을 새 실행에서 동시에 돌리고 조각 순서로 합친다
(조각마다 목표가 다르다). 단계 이름·입력은 그대로, `batchMode` 없는 이전 ledger는 순차.

수용 기준(합성): 거절된 지도·문제은행이 후속 한 번으로 완료된다 / 둘째 거절은 실패 / 끊긴 호출은 한 번 다시 돌고
결과가 끊기지 않은 실행과 같다 / 시간 초과·거절·한도·검사 실패는 다시 돌지 않는다 / 대조가 문제은행이 끝나기 전에 시작한다 /
문제은행 실패 뒤 재개는 문제은행만 부른다 / 자리 2개에서 셋째 세션은 기다리고 실패 뒤 자리가 돌아온다.

## 책임·입출력 계약·오류 상태
- `runner/root_front.py`: `checked`(호출+검사+후속), `_session`(transport-retry), `_receipt`, `audits`, `run`의 동시 줄.
- `quizbank/connection_generate_v3.py`: `Stages._call`(transport-retry), `intake_rejections(quiet)`.
- `quizbank/connection_generate_v4.py`: 추가 회차 커버 확인을 `batches.judgments`로.
- `quizbank/connection_batches.py`: `BATCH_WORKERS`·`_workers`.
- `studyez_llm/execution.py`: `slot`, `slot_limit`. `studyez_llm/codex.py`: `run`이 자리를 잡음, `network_failure`, `wait_for_network`.
- 오류: 실패 기록(`failure.json`, ledger `failed`)과 재개 요구는 그대로. 새 오류 종류 없음.

## 호환성과 데이터 보존
- 서버·DB·결과 형식·지시문·단계 입력 지문 변경 없음.
- 실행 지문(`connection_generate.identity`)에는 `quizbank/connection_*.py`와 `studyez_llm`의 코드 해시가 든다. 그래서 이 변경 전에
  시작해 멈춘 실행을 새 러너로 이으려면 지금 규칙대로 관리자 재개(`--resume <이유>`)가 한 번 필요하고, 입력이 같은 완료 단계는 그대로 재사용된다.
  러너를 바꿀 때마다 있는 일이며 이 변경이 더한 조건은 없다.
- 기존 산출물은 옮기거나 지우지 않는다. 새로 생기는 것은 `refused-*`, `check-failure.json`, `.net-*`, `.native/<단계>.net/`뿐이다.
- 수정 상한·판정·되돌리기·원본 보존 규칙 불변. 자동으로 다시 도는 것은 판정이 없었던 호출 하나(R3)와 기존 review-retry/1뿐이다.
- 다른 파이프라인(예습 덱 등)도 `codex.run`을 쓰므로 기계 전체 자리 수에 함께 든다. 8보다 적게 쓰는 지금은 동작이 같다.
