# Main-Quiz 생성 러너 일반화 — 구현 계획

## 변경 범위·대상 파일·순서

PR 셋으로 나눈다. 각 PR은 혼자 병합·배포해도 지금 동작을 깨지 않는다.

### PR A — 계약·엔진 (R3 일부, R4, R5)
1. 읽기 전용 대조: 두 공개 강의 결과(`runs/_e2e/26110803`, `26110901`의 result.json)가 지금 `validate_result`·`validate_all`을 통과하는지 기록한다. 이후 모든 단계의 기준선이다.
2. `studyez_contracts/roots/generation_v2.py`
   - `budgetPolicy` 검증(R4): 정책 표기가 있으면 `consumedRounds==0`이고 `n==total`이다. 없으면 지금 규칙이다.
   - `validate_review_retries`(R5)
   - `validate_stage_resumes`의 「다른 복구와 섞지 않음」에서 `reviewRetries`만 예외로 둔다.
3. `quizbank/connection_generate_v2.py`
   - 새 ledger에 `budgetPolicy`를 적고, 회차 루프 상한을 정책에 따르게 한다.
   - 검토 포기 두 경우를 감지하고, `.retry-<단계>/`에 보관한 뒤 새 세션으로 1회 다시 돌린다.
   - 마지막 회차 unknown은 조립 전에 감지한다. 재실행한 뒤 조립한다.
4. `initial_cost`를 가정하는 수동 복구 도구는 새 정책 ledger를 만나면 이유를 출력하고 거절한다.
   - 대상: `runner/root_*_recovery.py`, `quizbank/connection_authoring_recovery.py`, `runner/root_medical_retry.py`, `runner/root_importance_review.py`
5. 검사(먼저 쓰고, 수정 전에 실패하는 것을 확인한다)
   - 예산: 초기 오류 + repair-3까지, 옛 결과 통과, 정책을 섞은 manifest 거절
   - 재실행: 빈 판정 1회 뒤 통과, 2회면 실패, 마지막 unknown 1회, 보관·증명, 재개와 함께
   - 복구 도구 거절

### PR B — 앞 단계·파생 packet·러너 분기 (R2, R3, R6 러너 쪽)
1. `content/prompts/learning-links/`
   - 시범 `run.py`의 인라인 대조·보완 지시문과 스키마를 파일로 옮긴다. 강의 이름 자리만 변수로 바꾼다.
   - 검사: 변수를 사슬알균 값으로 채우면 시범 지시문과 바이트가 같다.
2. `studyez_contracts/roots/map_tree.py`(새 파일)
   - SCOPE 템플릿, `derive_packet(server_packet, front)`, `validate_front(manifest, server_packet)`
3. `runner/root_front.py`(새 파일)
   - 시범 `run.py`의 prepare~verify-points와 공통 장치(`call`, `finish`, `refs_ok`, `check_audit`, `postcheck`)를 packet 입력으로 옮긴다.
   - 경로 상수를 없앤다. 출력은 `runs/_root-generation/<gid>/front/`다.
   - `--resume <이유>`로 실패 단계부터 이어 간다.
4. `studyez_contracts/roots/generation_v2.validate_result`
   - `pipeline=='map-tree/1'`이면 `validate_front`로 파생 packet을 다시 만들고, 그 packet으로 기존 검증을 한다.
5. `runner/connection_generation.py`
   - map-tree면 `root_front` → 파생 packet 저장 → `root_native_json` 순서로 띄운다.
   - 서버가 준 이어 하기 이유를 두 하위 프로세스에 넘긴다.
   - 진행 카드(`parallel_status`)에 앞 단계를 표시한다.
6. `quizbank/connection_generate.py`(v1 진입 형식 검사)·v2: 새 `sourceAssessmentFormat`을 map-tree 분기로만 받는다.
7. 검사
   - 재생: 사슬알균 `runs/_e2e/26110901` 사본과 보관된 원응답을 가짜 codex로 돌린다. `root_front` 산출물이 시범과 같아야 한다.
   - 파생: 같은 서버 packet이면 같은 `inputHash`가 나오고, 필드를 바꾸면 거절된다.
   - 옛 러너 코드(PR B 이전 커밋)에 map-tree packet을 주면 모델 호출 전에 거절된다.
   - 이어 하기: front의 point 실패에서 다시 돈다.

### PR C — 서버·웹 (R1, R6 서버 쪽, R7)
1. `server/app/routes/root_generation.py`
   - `RequestIn.pipeline`: `Literal['map-tree/1'] | None`이다.
   - `resumeReason`: 이어 하기 시 필수다.
   - map-tree packet 필드: `pipeline`, 새 `sourceAssessmentFormat`, `privatePilot` 기본 false
   - 이미 공개된 판이 있는 강의는 409로 거절한다.
2. `server/app/routes/prequiz_jobs.claimed_job`: map-tree 요청에도 `rootGenerationId`와 이어 하기 이유를 붙인다.
3. `web/src/bank/RootGenerationPanel.tsx`
   - 기본 map-tree. 기존 방식은 「고급」 아래로 옮긴다.
   - 승인 문구에 보내는 자료·쪽수·호출 상한·예상 시간·「성공 시 학생 공개」를 넣는다.
   - 이어 하기에 이유 입력 칸을 둔다. 실패 사유를 표시한다.
4. `docs/development/README.md`: 「사람에게 묻는 것」 아래에 map-tree 관리자 요청이 그 강의의 승인이라는 한 줄과 근거 링크를 적는다.
5. 검사
   - 서버, 격리 로컬 DB
     - map-tree 요청의 packet 필드와 해시
     - 옛 요청 해시 불변
     - 이미 공개된 강의 409
     - 이어 하기 이유 전달
     - `put_result`가 map-tree 결과를 `allowed_users=[]`로 게시
     - 다른 강의·QuizBank·BankState·RootSession 해시 불변, 이벤트 +1
   - 웹: typecheck·build, 패널 문구·요청 본문 단위 검사

### 배포 뒤 (PR C 병합 이후)
1. 러너 배포 사본을 새 코드로 준비한다.
   - 옛 agent 프로세스는 pid로 직접 끈다. 예약 작업만 재시작하면 러너가 둘이 된다.
   - `runtime.json`으로 새 코드가 도는지 확인한다.
2. 첫 실제 실행은 사용자가 관리자 화면에서 강의를 골라 누를 때 한다. 이 작업이 대신 누르지 않는다.
   - 실행 기록·단계 시간·포기/재실행 여부·공개 결과는 `release.md`에 남긴다.

## 검사 명령과 성공 조건

worktree 루트에서, 메인 체크아웃의 계약이 섞이지 않게 `PYTHONPATH=.`으로 돌린다.

| 체크 | 명령 | 성공 조건 |
|---|---|---|
| contracts | `python -m pytest tests/contracts -q` | 새 검사 포함 전부 통과. 두 공개 결과 재검증 통과 |
| generation | `python -m pytest tests/quizbank -q` | 통과. 새 예산·재실행 검사는 수정 전 실패 기록이 있다 |
| runner | `python -m pytest tests/runner -q` | 통과. 재생 검사 포함, 모델 호출 0 |
| server | `server/.venv/Scripts/python.exe -m tests root` (`server/`에서) | 통과. `DATABASE_URL`은 격리 로컬 DB |
| web | `npm --prefix web run typecheck` · `npm --prefix web run build` | 통과 |

- 각 PR 마지막에 루트 전체(`python -m pytest tests`)를 한 번 돌린다.
- 기존에 실패하던 것(`test_desktop_control`)은 따로 표시하고, 새 실패와 섞지 않는다.

## 위험·복원·승인할 범위

**위험**
- **재생 검사가 시범과 다르게 나올 수 있다.**
  - 시범 `run.py`에는 생성 폴더 이름을 고정해 둔 잠재 버그가 있다(`results`·`status`).
  - 옮기면서 이 버그는 고친다. 그 밖의 차이는 버그로 보고 먼저 맞춘다.
- **서버 jokbo Asset이 시범 PDF와 다를 수 있다.** PR B 시작 전에 읽기 전용으로 sha를 대조하고 결과를 기록한다.
- **자동 공개에 품질 하한이 없다(열린 질문).** 첫 실행 결과를 보고 사용자에게 다시 묻는다.
- **노트북 잠자기.** 단계가 끊기면 R6로 이어 한다.

**복원**
- 코드는 git revert와 이전 Cloud Run revision·Pages로 되돌린다. DB 스키마 변경이 없어 되돌릴 데이터 구조가 없다.
- 러너는 이전 커밋으로 되돌려 재시작한다.
- 이미 게시된 map-tree 판은 관리자 publication 경로로 `enabled=false`로 닫을 수 있다. 판과 학습 기록은 지우지 않는다.

**승인할 범위**
- 개발 루프(`docs/development/README.md`)에 따라 사용자의 작업 요청이 PR A·B·C의 구현·검사·PR·병합·배포 승인이다.
  - 병합은 API·웹을 자동 배포한다. 운영 DB 스키마 변경은 없다.
- 다음은 이 계획이 하지 않는다.
  - 실제 강의 자료를 Codex로 보내는 일
  - 학생 공개
  - 위 둘은 사용자가 관리자 화면에서 강의마다 요청할 때만 일어난다(결정 3·4).
- 이미 공개된 두 강의의 판 교체·재생성은 범위 밖이다.
