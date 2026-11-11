# Main-Quiz /4 정규화: 성분을 따로 채점할 사실 하나씩 — 설계

## 요구사항과 수용 기준

- R1. /4 normalize 지시문은 `automation/extract-v2.md`를 복사하고 다음만 더한다.
  - component 하나는 따로 물어 채점할 수 있는 내용 하나다. 포인트 문장·answer_scope 전체를 한 component에 옮기지 않는다.
    한 번에 기억해야 의미가 있는 하나의 기전·짧은 같은 범주 목록·실제 종합 판단만 한 component로 둔다.
  - 해석상 주의(「일반화하지 않는다」「~와 구별한다」)는 그 자체를 판단 목표로 설계한 경우가 아니면 component에 넣지 않는다.
  - 지도 관계 방향은 포인트 방향이 그 관계를 이미 회상시키면 따로 만들지 않는다.
    cue는 구체적인 답이 있는 질문이며, 개념 이름만 끼운 틀을 쓰지 않는다.
  - 예시는 실제 강의 내용이 아닌 일반 예(약물의 표적·경로·부작용)를 쓴다.
- R2. 러너(`runner/root_native_json.task_for`)는 단계 이름 `normalize`이고 입력의 `_pipeline_version`이
  `root-generation/4`일 때만 v4 지시문을 읽는다. 그 밖(/2·/3·버전 없음)은 지금처럼 `extract-v2.md`다.
- 수용: 새 검사(`tests/runner/test_root_native_v3.py`)와 전체 회귀가 통과한다. 재생 결과를 release.md에 남긴다.

## 책임·입출력 계약·오류 상태

- 출력 스키마(`generation_v2.BRIEF`)·수용 검사(`check_file`, `brief_findings`)·누락 점검 규칙은 바꾸지 않는다.
  component는 이미 배열이다.
- `_pipeline_version`은 `connection_generate_v3.Stages.run`이 모든 단계 입력에 넣는 값이다(/4는 `root-generation/4`).

## 호환성과 데이터 보존

- /4 ledger의 identity는 `v3/`·`v4/` 지시문 해시를 포함한다(`_prompt_hash`). 새 파일로 identity가 바뀌므로
  실패·중단된 기존 /4 실행을 이어 가려면 지금처럼 `--resume <이유>`가 필요하다. 이어 가도 normalize는
  입력 해시가 같으면 저장된 결과를 다시 쓴다(새 지시문은 새 실행부터).
- 이미 만든 판·운영 DB·runs 기록은 바꾸지 않는다.
