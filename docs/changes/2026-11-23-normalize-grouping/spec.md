# Main-Quiz /4 정규화: 포인트를 강의 뼈대로 묶어 목표를 짠다 — 설계

## 요구사항과 수용 기준

- R1. `v4/normalize.md`에 「목표의 뼈대」 문단을 더한다.
  - 목표는 포인트 목록을 차례로 옮긴 것이 아니라 강의의 뼈대다. 포인트는 목표의 근거이며 1:1이 아니다.
    같은 질문 축을 공유하는 포인트는 한 목표로 묶고, 상위 비교와 세부를 함께 담은 포인트는 각 목표에 붙인다
    (`points[].target_ids` 여럿).
  - root: 강의가 여러 갈래를 묶는 큰 축(여러 대상을 같은 기준으로 비교·분류, 갈래를 잇는 감별).
    branch: 아래 개념을 거느린 갈래의 질문. leaf: 따로 회상할 세부. 축과 개수는 강의에서 정하고 고정 비율·틀이 없다.
  - root·branch도 구체적인 답이 있는 질문이다. 묶은 목표가 묻는 답을 leaf로 다시 묻지 않는다.
  - 관계는 원본이 비교·인과·순서·선행을 말하면 그 kind로 쓴다. association은 소속·대응에 쓴다.
  - 답 조각 하나하나를 개념으로 만들지 않는다. 개념은 지도 개념 또는 다른 목표·관계가 가리킬 이름 있는 내용이다.
  - 목표 설계를 포인트 순서의 반복으로 찍어내지 않는다. 코드는 입력을 그대로 옮기고 형식을 맞추는 데만 쓴다.
- R2. Map 문단의 「그 관계를 이미 포인트에서 온 방향이 회상시키면 … 따로 만들지 않는다」를
  「이미 다른 목표(포인트를 묶은 root·branch 포함)가 회상시키면」으로 넓힌다. 중복 금지는 그대로이고,
  묶은 목표를 만들지 말라는 뜻이 아님을 밝힌다.
- R3. 11-11 규칙(component 하나 = 따로 채점할 내용 하나, 해석상 주의는 component 밖, 이름만 끼운 cue 금지)과
  11-15 존재 목표 문단은 그대로 둔다.
- R4. `v4/PROVENANCE.md`에 이 변경을 한 문단으로 적는다. 검사(`tests/runner/test_root_native_v3.py`)에
  /4 지시문이 R1 문장을 담는지 확인을 더한다.
- 수용: 전체 회귀가 기존과 같고, 261118_05 재생에서 intent의 성공 기준을 release.md에 기록한다.

## 책임·입출력 계약·오류 상태

- 출력 스키마(`generation_v2.BRIEF`)는 이미 `role`(root/branch/leaf)·relation `kind`
  (association/comparison/causal/sequence/prerequisite)·`points[].target_ids` 배열을 가진다. 바꾸지 않는다.
- 수용 검사(`check_file`, `brief_findings`, `relation_findings`)·누락 점검(component 합집합)은 그대로다.
  묶은 목표의 component도 같은 규칙으로 판정된다.
- 웹·Work 입력(같은 지시문 + WEB TRANSPORT)도 이 지시문을 쓴다.

## 호환성과 데이터 보존

- /4 ledger identity가 지시문 해시를 포함한다(`_prompt_hash`). 병합·러너 재설치 뒤 실패·중단된 /4 실행을
  이어 가려면 `--resume <이유>`가 필요하다. 이어 가도 normalize 입력 해시가 같으면 저장된 결과를 쓴다.
- 이미 만든 판·운영 DB·runs 기록은 바꾸지 않는다. 재생은 git 밖 짧은 경로(`C:\sez\ng\`)에 쓴다.
- /2·/3과 `automation/extract-v2.md`는 그대로다.
