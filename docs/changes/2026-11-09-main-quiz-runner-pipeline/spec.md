# Main-Quiz 생성 러너 일반화 — 설계

## 지금 있는 것과 없는 것

조사는 2026-11-09, master 95482162 기준이다.

**이미 끝까지 이어져 있는 경로**
1. 관리자 버튼(`web/src/bank/RootGenerationPanel.tsx`)을 누르면 `POST /api/admin/root-learning/lectures/{subject}/{run_id}/generation`이 간다.
2. 서버(`server/app/routes/root_generation.py`)가 원본을 고정한다.
   - S1은 `notes_current` Asset, S2는 `jokbo` Asset이다. sha256과 크기를 적고, R2에 사본을 둔다.
   - 그 결과로 packet(`revision='auto-<gid>'`)을 만든다.
3. 러너가 일감을 받는다(`runner/agent.py` → `runner/connection_generation.run_generation`).
   - 원본을 받아 지문을 확인한다.
   - 하위 프로세스 `python -m runner.root_native_json --packet --out`을 띄운다.
4. `PUT /api/admin/root-generation/{id}/result`가 결과를 검증하고 바로 게시한다.
   - `privatePilot`이면 요청한 관리자에게만 열고, 아니면 전체에 연다.

**이 경로에 없는 것** — 두 시범이 성공한 앞 단계다.
- 버튼의 기본값(source + parallel)은 `quizbank/connection_parallel.py`로 지도·포인트·은행을 /2 형식으로 동시에 뽑는다.
- 다음 단계들이 없다.
  - 개념 지도 /3: parent_id 트리
  - 포인트 /3: importance_basis
  - 포인트 대조 → 보완 ≤1 → 재대조
  - `speedStages`(맥락 검사 단계)
- 시범의 앞 단계는 `docs/changes/2026-11-09-main-quiz-second-lecture/run.py` 안에 직접 짜여 있다. 강의 상수는 다음과 같다.
  - SUBJECT, RUN_ID, TITLE, REVISION
  - SOURCES: 경로, sha, 쪽수
  - SCOPE 문장
  - 「감염병리1」 같은 라벨

## 요구사항과 수용 기준

### R1. 새 생성 방식 `map-tree/1` (결정 3)
- 관리자 버튼의 기본값을 `map-tree/1`로 바꾼다.
  - 요청 본문은 `inputMode:'source', authoring:'cli', pipeline:'map-tree/1'`이다.
  - 기존 parallel /2와 provided 방식은 「고급」 아래에 그대로 남긴다. 동작도 바꾸지 않는다.
- 버튼 옆에 요청 전에 다음을 표시한다. 버튼을 누르는 것이 그 강의 하나의 승인이다.
  - 보내는 자료: S1 파일명·쪽수, S2 파일명·쪽수
  - 보내는 곳: OpenAI Codex CLI
  - 호출 상한: 지도 1, 포인트 1, 대조 ≤2, 포인트 보완 ≤1, 출제 1, 보완 ≤3, 검토 단계마다 자동 재실행 ≤1
  - 예상 시간: 약 1~1.5시간. 실측이 쌓이면 고친다.
  - 성공하면 학생에게 바로 공개된다는 문구
- 승인한 관리자 id와 시각은 이미 남는다: `root_generation`의 `user_id`·`created_at`, packet의 `owner`. 새 칸은 없다.
- 서버 packet의 `sourceAssessmentFormat`은 새 값 `source-assessment/2-map-tree/1`이다.
  - 옛 러너는 모르는 형식을 모델 호출 전에 거절한다(`runner/CLAUDE.md:4`의 기존 동작). 그래서 옛 러너가 map-tree 요청을 parallel처럼 돌리는 일이 없다.
- 수용
  - `RequestIn`이 `pipeline`을 받는다.
  - `pipeline`은 packet과 `inputHash`에 들어간다.
  - 옛 요청(`pipeline` 없음)의 packet 해시는 그대로다.
  - 지금 러너 코드에 map-tree packet을 주면 모델 호출 없이 거절된다.

### R2. 러너가 앞 단계를 돈다
- 러너는 packet의 `pipeline=='map-tree/1'`을 보고 하위 프로세스 `python -m runner.root_front --packet --out`을 먼저 띄운다.
- 이 프로세스는 시범 `run.py`의 단계를 같은 순서·같은 지시문·같은 검사로 돈다.
  - 순서: prepare → map → point → audit → (issues가 있으면) repair → final-audit → verify-points → derive
  - 각 단계는 입력 해시를 고정하고, 영수증을 확인하고, `state.json`/`failure.json`을 남긴다.
  - 단계 자체에 자동 재시도는 없다. R5의 검토 포기만 예외다.
- 강의 상수는 packet에서 얻는다. 손으로 적지 않는다.

  | 시범 상수 | 일반화된 출처 |
  |---|---|
  | SUBJECT·RUN_ID | packet `subject`·`runId` |
  | TITLE | packet `title`(서버 `Lecture.title`) |
  | REVISION | 서버의 `auto-<gid>` 그대로 |
  | SOURCES | packet `sources`(서버가 고정한 Asset). 받은 사본의 sha·크기를 확인하고, 쪽수는 PDF에서 센다 |
  | SCOPE | 아래 템플릿 + 관리자가 적은 `scope` |
  | 쪽 범위 문구 | 쪽 수에서 만든다(P2 `run.py:242`의 일반화) |
  | 출력 폴더 | `runs/_root-generation/<gid>/front/`, 생성은 `.../<gid>/` |

- SCOPE 템플릿에는 강의 고유 사실을 넣지 않는다. 시범 SCOPE의 구조만 남긴다.
  - 「올해 필기 S1 전체(N쪽, 「제목」)가 이 강의 범위다.」
  - 「S2는 족보 PDF(M쪽)다. 머리 표시의 연도·교수 구분을 따르고, 올해 같은 교수 기출을 우선한다.」
  - 「S1이 다루지 않는 S2 문항은 범위 밖이다.」
  - 그 뒤에 시범 packet이 SCOPE 뒤에 붙인 고정 문구(Map 계층 보존, 포인트 ID 보존 등)를 그대로 붙인다.
- 시범 `run.py`에 인라인으로 있던 대조·보완 지시문과 스키마는 `content/prompts/learning-links/`의 파일로 **글자 그대로** 옮긴다. 강의 이름 자리만 변수로 바꾼다. 출제 정책은 바꾸지 않는다.
- 수용 (모델 호출 없음)
  - 사슬알균 시범의 보관된 원본 응답(`runs/_e2e/26110901/`)을 가짜 codex로 재생한다.
  - 그러면 `root_front`가 시범과 같은 `concept-map.json`·`exam-points.json`·`audit.json`·최종 포인트를 낸다.
  - 지시문 파일은 강의 이름 자리를 빼면 시범 지시문과 바이트가 같다.

### R3. 파생 packet과 결과 검증
- `derive`는 서버 packet에서 생성기 packet을 결정적으로 만든다. 시범 packet과 같은 형태다.
  - `inputMode:'provided'`, `conceptMap`·`points`(앞 단계 최종본 원문), `speedStages:true`, `sourceAssessmentFormat:'source-assessment/2'`, `scope`(템플릿 결과)
  - 나머지 필드(`generationId`·`revision`·`subject`·`runId`·`title`·`sources`·`examDate`·`privatePilot`)는 서버 packet 그대로다.
- 이 함수는 `studyez_contracts/roots/map_tree.py`에 둔다. 서버·러너·생성기가 같은 것을 쓴다.
- 결과 manifest에 `frontStages` 증명을 싣는다.
  - 내용: 단계별 input/output/raw 해시, 지시문 파일 해시, 파생 packet과 그 `inputHash`
- `validate_result(result, server_packet)`의 동작
  - `pipeline=='map-tree/1'`이면 `frontStages`로 파생 packet을 다시 만든다.
  - 해시가 같은지 확인한 뒤, 기존 검사를 파생 packet에 대해 그대로 돌린다.
  - `pipeline`이 없는 packet은 지금과 똑같이 검증한다.
- 수용
  - 감염병리1·사슬알균 공개 결과가 바뀐 `validate_result`·`validate_all`을 그대로 통과한다.
  - 파생 packet의 필드 하나를 바꾼 결과는 거절된다.

### R4. 보완 예산 — 초기 지도 교정은 따로 센다 (결정 1)
- 새 정책 `initial-correction-separate/1`을 둔다. 생성기가 새 ledger를 만들 때 `budgetPolicy`로 적는다.
  - 대상: 새로 시작하는 모든 root-generation/2 실행. map-tree에만 한정하지 않는다.
- 이 정책에서 달라지는 것
  - 초기 지도 오류는 지금처럼 출제 단계 입력(`initialBriefErrors`)으로 가고 `validate_initial_correction`을 거친다.
  - `repairRounds`에는 더하지 않는다.
  - 회차 루프는 `range(start_round, 4)`다. 보완 단계는 최대 `repair-1..3`이다.
  - manifest `initialMapCorrection`은 `{errors, consumedRounds:0, budgetPolicy}`다. 오류 목록은 그대로 남긴다.
- 정책 표기가 없는 ledger와 결과는 옛 규칙(초기 교정 = 1회)으로 읽는다.
  - 진행 중이던 실행을 이어 해도(`--resume`) 정책이 바뀌지 않는다. 상한을 재실행으로 초기화하지 않는다.
- 기존 수동 복구 도구는 새 정책 ledger를 거절하고 이유를 출력한다. 대상은 `root_*_recovery`, `connection_authoring_recovery`, `root_medical_retry` 등 `initial_cost`를 가정하는 도구다. 맞춰 고치는 일은 범위 밖이다.
- 수용
  - 초기 오류가 있는 가짜 실행이 repair-3까지 돈다.
  - 옛 결과 두 개는 계속 통과한다.
  - 정책을 섞은 manifest(정책 표기 + `consumedRounds:1`, 또는 표기 없이 repair-4)는 거절된다.

### R5. 검토 포기 — 새 세션 1회 자동 (결정 2)
- 새 정책 `review-retry/1`이다. 포기는 다음 둘로만 정한다. 비율 선은 쓰지 않는다(시범 진단: 비율은 판정 몇 개로 넘을 수 있다).
  1. `source-n`이 `require_judgment` 거절로 실패한 경우. 같은 세션 되돌려주기를 한 번 하고 난 뒤다.
     - 거절 조건: 문항 판정 전부 doubt, 점검 전부 unknown, direction_evidence 비어 있음
  2. 결과 조립이 마지막 회차 원본 대조의 `clinical_context_status=='unknown'` 때문에 거절된 경우
     - `conflict`는 포기가 아니다. 지금처럼 보완 사유이거나 실패다.
- 처리
  - 그 단계의 작업 폴더를 `.retry-<단계>/`로 옮겨 보관한다. 지우지 않는다.
  - 같은 입력으로 새 Codex 세션을 한 번 띄운다.
  - ledger `reviewRetries`에 다음을 남긴다: 단계, 사유 종류, 이전 단계 기록, 이전 raw 해시
  - 보완 횟수와 회차 번호는 바뀌지 않는다.
- 한 단계에 한 번뿐이다. 다시 포기하면 생성은 실패로 멈춘다.
  - 서버 상태: `failed`, 사유 문구 「원본 대조 포기 2회 — 관리자 확인 필요」
  - 웹 패널에 그 사유가 보인다.
- 계약 `validate_review_retries`가 검사한다.
  - 다시 돈 단계의 입력 해시가 이전과 같아야 한다.
  - raw는 달라야 한다.
  - 다른 단계는 바뀌지 않아야 한다.
  - 단계당 1회여야 한다.
- `stageResumes`와 함께 있는 것을 허용한다. 지금 `validate_stage_resumes`는 다른 복구 이력과 섞이는 것을 거절하므로 `reviewRetries`만 예외로 둔다. 나머지 이력과는 지금처럼 섞지 않는다.
- 맥락 검사(`context-n`)는 자동 재실행 대상이 아니다.
  - unknown은 이미 정답 검수를 막지 않는다(clinical-context/2).
  - 첫 메시지에 이미지를 붙인 뒤로는 포기 원인이 원본 대조와 같다고 본 근거가 없어졌다.
  - 관측하다 필요해지면 따로 연다.
- 수용
  - 빈 판정을 내는 가짜 source 단계가 한 번 자동으로 다시 돌고 통과한다.
  - 두 번 빈 판정이면 실패로 멈춘다.
  - 마지막 회차 unknown도 한 번 다시 돈다.
  - 보관 폴더와 ledger 증명을 계약이 받아들인다.

### R6. 사람이 이어 하기
- 생성이 실패·보류로 멈추면 웹 패널의 「이어 하기」로 다시 연다. 이때 이유 칸이 필수다.
- 서버는 이유를 일감에 싣는다. 러너는 이를 `--resume "<이유>"`로 넘긴다.
- 앞 단계에서 멈췄으면 `root_front`도 같은 방식으로 실패 단계부터 이어 간다.
- 이어 하기는 회차·보완 상한·자동 재실행 이력을 초기화하지 않는다.
- 수용: 앞 단계 point 실패와 생성 단계 source-1 실패, 두 지점에서 각각 이어 하기가 실패 단계부터 다시 돈다.

### R7. 공개 (결정 4)
- `map-tree/1` 요청의 `privatePilot` 기본값은 false다.
  - 결과가 `validate_result`를 통과하면 기존 `put_result`가 `allowed_users=[]`로 학생에게 연다.
  - 기존 가드는 그대로 쓴다: 활성 일감, 기준 control 해시, 원본 불변, 과제 ≥1, revision 중복 없음.
- **이미 공개된 판이 있는 강의**는 map-tree 요청을 409로 거절한다.
  - 문구: 「이미 공개된 Main-Quiz 판이 있습니다. 판 교체는 학습 기록 승계 문제가 있어 별도 승인이 필요합니다」
  - 이유: `put_result`는 `control.revision`을 새 판으로 바꾼다. 감염병리1·사슬알균 학생의 학습 기록과 판의 관계를 이 작업에서 정하지 않는다(bank_retention).
- 시범 반입 스크립트가 했던 사후 대조를 서버 검사로 옮긴다. `put_result` 한 트랜잭션이 대상 강의 밖의 것을 바꾸지 않아야 한다.
  - 다른 강의의 RootContent·RootControl
  - QuizBank
  - BankState
  - RootSession
- 수용: 격리 로컬 DB에서 두 강의를 만든다. 한 강의에 map-tree 결과를 게시한다. 다른 강의와 Quiz Bank·학습 상태의 해시가 같고, 대상 강의의 이벤트가 정확히 하나 늘고, `allowed_users==[]`다.

## 책임·입출력 계약·오류 상태

| 구성 | 책임 | 바뀌는 것 |
|---|---|---|
| web `RootGenerationPanel` | 승인 문구·호출 범위 표시, 기본 map-tree, 이어 하기 이유 | 화면·요청 본문 |
| server `root_generation.py` | `pipeline` 받기, 이미 공개된 강의 거절, 이어 하기 이유 전달, 결과 검증·게시 | RequestIn 필드 2개(`pipeline`, `resumeReason`), 거절 1개. DB 스키마 변경 없음(packet은 JSON 칸) |
| server `prequiz_jobs.claimed_job` | map-tree 요청에 `rootGenerationId` 붙이기 | 조건 1줄 |
| runner `connection_generation` | map-tree면 `root_front` → `root_native_json` 순서로 하위 프로세스 | 분기·이어 하기 이유 |
| runner `root_front`(새 모듈) | 앞 단계·파생 packet | 시범 `run.py`에서 옮김 |
| quizbank `connection_generate_v2` | 예산 정책, 검토 포기 재실행 | 회차 루프·ledger |
| contracts `roots/map_tree.py`(새)·`generation_v2.py` | 파생 packet, 예산·재실행·frontStages 검증 | 새 정책 3개 |
| content/prompts/learning-links | 대조·보완 지시문 파일 | 인라인 → 파일, 문구 불변 |

- 실패 상태는 성공과 구분한다.
  - 앞 단계 실패: 서버 `failed`, 메시지 「앞 단계 <단계> 실패: <사유>」
  - 생성 실패: 지금 메시지 그대로
  - 검토 포기 2회: R5
  - 이미 공개된 강의: 요청 시 409
  - 원본이 바뀜: 지금처럼 `put_result` 409
- 노트북이 잠들면 단계 시한이 끊길 수 있다. 끊기면 실패로 남고 R6로 이어 한다. 잠들지 않게 하는 것은 이 작업 밖이다.

## 호환성과 데이터 보존
- 공개된 두 강의(261104_02, 261105_01)의 판·학습 기록·이벤트는 건드리지 않는다. 두 결과는 바뀐 계약에서도 그대로 검증을 통과해야 한다.
- `runs/_e2e/*` 시범 기록은 읽기만 한다. 재생 검사는 사본으로 한다.
- 운영 DB 스키마는 바꾸지 않는다. 검사는 격리된 로컬 DB와 저장소로 한다.
- 옛 packet(`pipeline` 없음)과 옛 ledger(`budgetPolicy` 없음)는 옛 규칙으로 읽는다.
- 러너 배포 사본은 git 병합으로 갱신되지 않는다. 새 러너를 먼저 준비하고, 옛 프로세스를 끈 뒤 확인한다.
  - 그 사이 옛 러너가 map-tree 요청을 받아도 새 `sourceAssessmentFormat` 때문에 모델 호출 전에 거절한다(R1 수용).

## 개발 루프의 「사람에게 묻는 것」과의 관계
- `docs/development/README.md`는 두 가지를 묻게 한다.
  - 정해진 자동 경로 밖에서 강의 자료를 외부 모델로 보내는 것
  - 학생에게 새로 공개되는 범위
- 이 작업은 관리자 화면 요청을 그 강의 하나에 대한 두 승인으로 정한다(사용자 2026-11-09 결정 3·4). 화면이 범위를 구체적으로 보이므로 「구체적 범위로 묻는다」를 지킨다.
- README에 이 경로를 정해진 자동 경로로 한 줄 적는다. 블럭 단위 일괄 승인은 아니다.

## 열린 질문 (구현을 막지 않음)
- **품질 하한.** 지금 자동 공개의 가드는 과제 ≥1뿐이다. 사슬알균은 목표 79/119가 준비된 판으로 공개됐다. 하한(예: 준비 목표 비율)을 둘지는 첫 자동 실행 결과를 보고 정한다.
- **중요도 보완(`root_importance_review`).** 시범에서도 `all`에 들어 있지 않은 선택 단계였다. 자동 경로에는 넣지 않는다.
- **족보 section을 여러 강의가 함께 쓰는 경우.** 예: 261104_02/03/05가 S7-8을 공유한다. SCOPE의 「S1이 다루지 않는 S2 문항은 범위 밖」 한 줄로 처리한다. 첫 공유 강의 실행에서 확인한다.
- **서버 jokbo Asset 바이트가 시범의 교수우선 v2 PDF와 같은지.** 구현 첫 단계에서 두 강의로 읽기만 하고 대조한다. 다르면 서버 쪽 자료를 따르고 차이를 기록한다.
