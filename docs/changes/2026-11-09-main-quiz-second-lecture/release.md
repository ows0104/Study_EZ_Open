# Main-Quiz 생성 두 번째 강의 시범 — 사슬알균 — 실행 기록

실행 폴더: `runs/_e2e/26110901/` (메인 체크아웃, git 밖). 코드: 이 worktree.

## 앞 단계 (2026-11-09 02:49–03:07, 18분, 멈춤 없음)

| 단계 | 결과 |
|---|---|
| prepare | S1 38쪽 · S2 8쪽 고정 |
| Map /3 | 개념 57 · 뿌리 6 · 깊이 3 · 관계 30 (4분) |
| 포인트 /3 | 81 (5분) |
| 대조 | needs_revision 10 — overmerged 5 · unsupported 4 · missing 1 |
| 보완 1회 | 89 |
| 재대조 | needs_revision 6 — 기록만(감염병리1과 같은 처리) |
| packet | `map-tree-26110901`, speedStages |

모델이 notes에 남긴 자료 충돌은 다음과 같다.
- 백신: 다당 vs 접합
- 비말 전파: 드물다 vs 없다
- catalase 감별
- 2025 참고 기출 정답 번호: 30·100번 vs 4·11번

모델은 이 충돌들을 지우지 않았다.

## generation/ — 실패 1 (03:07–03:32)

normalize → generate(106문항, 그림 8) → context-0 → source-0 ‖ medical-0 → 보완 사유(required_gap 등) → **repair-1 거절**.

결함 두 개가 겹쳤다. 둘 다 강의와 무관한 엔진 결함이다.

1. **보완 입력에 렌더러 소유 `stimuli`가 들어갔다.**
   - generate의 raw에는 `stimuli`가 0개였다. 렌더러가 `visual_stimuli`로 8개를 붙인 은행이 repair-1 입력 `bank`·`previousAuthoring.bank`로 갔다.
   - 모델은 지시대로 바뀌지 않은 문항을 그대로 베꼈다. 저작 스키마(`AUTHOR_BANK`는 `stimuli`를 뺀다)가 전체를 거절했다.
   - 감염병리1에는 그림 문항이 없어 이 길을 지나지 않았다.
2. **어댑터의 스키마 검사가 같은 세션 되돌려주기(#41)보다 앞에 있었다.**
   - 그래서 스키마 오류는 되돌려주기 없이 바로 실패했다.
   - 베낀 `stimuli`를 빼면 그 뒤에 `recall units must partition every component exactly once`가 하나 더 있었다. 되돌려주기가 잡았어야 할 종류다.

수정은 다음과 같다(c0f5a48a).
- `connection_visuals.authored`: 보완 단계 입력은 저작 형태(`stimuli` 없음)로 준다. 그림 선택은 `previousAuthoring.visual_stimuli`로 그대로 간다.
- `root_native_json`: 되돌려주기를 쓸 수 있으면 스키마 오류도 `check_file` 오류로 같은 세션에 한 번 되돌려준다. 쓸 수 없는 검사 환경은 지금처럼 바로 실패한다.
- 검사: 새 2개. 둘 다 수정 전에는 같은 오류로 실패한다.
- 결과: 루트 2,182 통과(제외 `test_desktop_control`), `map_numbers --check` 정상.
- 서버·계약 변경은 없다.

`generation/`은 보존한다. 사용량은 repair-1까지 1/3을 썼다. 2026-11-09 사용자 「generation-2로 다시」에 따라 같은 packet으로 `generation-2/`에서 다시 돈다.

## generation-2 — 실패 2 (같은 packet, c0f5a48a 코드)

normalize(초기 지도 오류 1 → 보완 1/3 선소비) → generate(89문항) → context-0 → source-0 ‖ medical-0
→ **repair-1 통과**(위 수정 확인) → context-1 → source-1 ‖ medical-1 → **repair-2(3/3, 마지막) 거절**.

- 원인: 모델이 `result.json` 앞에 UTF-8 BOM을 썼다. 영수증 해시는 맞았지만 어댑터가 엄격한 utf-8로 읽다 실패했다.
  감염병리1 26110803 audit에서도 같은 BOM이 나온 적이 있다(그때는 run.py의 postcheck로 처리).
- 수정(52e1e751): `root_native_json.read_model`은 모델이 쓴 파일의 맨 앞 BOM 하나를 허용한다. 바이트와 영수증은 그대로다.
  `artifact`·`check_file`·`validate_stage`·tier 복구·task supplement가 이를 쓴다. 검사 1개를 더했다(수정 전 실패).
- 이 폴더를 재호출 없이 이어 가려면 계약의 형식 복구(`validate_format_recoveries`, tier 표기 전용)에 새 종류를 더해야 한다.
  아직 하지 않았다.

### 내용 신호: 중요도 근거 다툼이 마지막 회차에 몰렸다

| 회차 | target_checks | 보완 사유 |
|---|---|---|
| source-0 | unknown 118 · conflict 1 | question_fix 34 · map_fix 4 · required_gap 3 |
| source-1 | consistent 60 · unknown 31 · conflict 28 | question_fix 14 · **map_fix 68** · required_gap 16 |

- source-1의 map_fix는 대부분 「목표 X의 근거를 별도로 판단한다」였다.
  예: 포인트가 S1 7쪽 Summary를 `learning_objective`로 적었는데 「Summary 본문은 2쪽의 명시적 학습목표가 아니다」.
- 포인트 /3 단계의 importance_basis 판정을 원본 대조가 두 번째 회차에서야 본격적으로 다투었다.
  그 결과 98건이 마지막 보완 1회에 실렸다.
- 감염병리1 26110803에서는 최종 conflict가 7이었다.

## generation-3 — 보완 3/3 소진, 최종 정답 검수 보류 (결과 없음)

같은 packet이고 코드는 52e1e751(수정 3건 모두)이다. 엔진 결함으로 멈춘 곳은 없었다.

| 회차 | context(임상 정리 확인) | medical(독립 정답 검수) | source 지적 |
|---|---|---|---|
| 0 | consistent | 완료(round-0 은행) | required_gap 45 · map_fix 34 · question_fix 14 |
| 1 | **unknown** — 「나머지 PNG를 직접 대조한 근거가 없다」 | **blocked**(보완 사유 아님) | question_fix 3 |
| 2 | **conflict** — repair-2가 Q107·Q108 해설에 「P018의 … 보완」 같은 저작 이력을 썼다 | **blocked** | required_gap 2 · map_fix 1 · question_fix 1 |

- 보완 예산: 초기 지도 교정 1회 + repair-1 + repair-2 = 3/3.
  마지막 회차가 blocked여서 생성기는 설계대로 게시하지 않고 멈췄다(「독립 정답 검수 입력 분리가 완료되지 않았습니다」).
- 내용은 수렴했다(최종 source 지적 4건). 그러나 **최종 은행에는 독립 정답 검수가 한 번도 돌지 않았다.**
- target_checks: source-0만 판정했다(consistent 87 · conflict 32). source-1·2는 119개 전부 unknown이었다.
  같은 지시문인데 회차마다 판정 범위가 다르다.

## 시범에서 나온 것 (요약)

엔진 결함 3건은 고쳤다(c0f5a48a · 52e1e751). 검사는 새 3개이고 수정 전에는 실패한다.
1. 보완 입력의 렌더러 소유 `stimuli`(그림이 있는 강의에서 처음 지남)
2. 스키마 오류가 같은 세션 되돌려주기를 건너뜀
3. 모델 파일의 UTF-8 BOM

일반화 전에 정해야 할 것(설계 결정, 미착수):
- **해설의 저작 이력**:
  - 해설에 포인트·문항 ID나 「보완」 경위가 들어가면 check_file에서 잡아 같은 세션으로 되돌릴지 정해야 한다.
  - 계약(`validate_authoring`)에 넣으면 이미 완료된 결과의 재검증에 영향이 있는지 먼저 확인해야 한다.
- **context `unknown`의 처리**:
  - 지금은 근거 없이 미뤄도 그 회차의 정답 검수가 조용히 빠지고, 보완 사유도 생기지 않는다.
  - 한 번 다시 묻거나 사유로 올릴지 정해야 한다.
- **초기 지도 교정의 예산 선소비**: 두 실행 모두 1/3을 먼저 써서, 실제 보완은 두 번뿐이었다.
- **원본 대조의 판정 범위 흔들림**: target_checks를 회차마다 전부 판정하거나 전부 미루었다. 그래서 중요도 근거 다툼(generation-2의 map_fix 68)이 어느 회차에 몰릴지 예측할 수 없다.

운영 반입·학생 공개는 하지 않았다. 결과(`result.json`)가 없다.

## 후속: 해설 저작 이력 검사 (2026-11-09 사용자 「해설 저작 이력 검사」)

- `quizbank/authoring_text.internal_id_mentions`가 학생에게 보이는 칸에서 이번 실행의 내부 ID를 찾는다.
  - 학생 칸: question·answer·answer_units·explanation·options·option_explanations·matching·sequence.
  - 내부 ID: 문항·포인트·개념·목표·방향·관계. 글자와 숫자를 모두 가진 ID만 센다. 그래서 P450·C5a·「A군」은 세지 않는다.
- `root_native_json.check_file`(generate·repair)이 이를 검사한다. 걸리면 같은 세션에 한 번 되돌려 의학적 설명으로 고치게 한다.
  - 계약(`validate_authoring`)과 생성기의 수용 판정은 바꾸지 않았다. 남은 것은 지금처럼 임상 정리 확인이 conflict로 잡는다.
  - 기존 결과의 재검증에는 영향이 없다.
  - 문항을 그대로 복사해야 하는 brief-repair 복구와, 원문을 보존하는 웹·독립 은행 generate에는 적용하지 않는다.
- 기존 결과물 13개 측정:
  - 감염병리1(공개 판 포함): 0건
  - 사슬알균 generate: 0건
  - 사슬알균 보완 출력: 3건(Q107·P018, Q108·P020, Q014·Q015)
  - 학생 칸 밖의 ID와 의학 표기는 세지 않았다(오탐 0)
- 검사: 새 2개(찾기 단위 1·같은 세션 되돌려주기 1), 둘 다 수정 전 실패. 루트 2,185 통과, `map_numbers --check` 정상.

## generation-4 (2026-11-09 사용자 「generation-4 돌려줘」, 병합된 #53 코드)

- 앞 실행과 같은 packet으로 11:08–12:12에 64분 돌았다. 결과는 보류이고 `result.json`은 없다.
- 고친 4건은 모두 통했다. 정규화·출제·repair-1·repair-2가 형식 오류 없이 지났다.

| 회차 | context | medical | source |
|---|---|---|---|
| 0 | consistent | 완료 — 102문항 ok 82 · doubt 16 · wrong 4 | 판정 있음(ok 92 · doubt 10, 지적 71) |
| 1 | **conflict** — CF04 출처 쪽(26–27·29쪽)이 섞임 | **blocked** | 판정 있음(ok 112 · doubt 13 · wrong 4, 지적 78) |
| 2 | **conflict** — CF04에서 「but not with urine」 누락, Q037 충돌 기록 없음 | **blocked** | **빈 판정** — 129문항 전부 doubt, 점검 전부 unknown, 지적은 limitation 2건 |

- 보완 예산: 초기 지도 교정 1회 + repair-1 + repair-2 = 3/3.
- context는 회차마다 **다른** 누락을 찾았다. 그래서 정답 검수가 0회차 뒤로 다시 돌지 못했다(설계 결정 대기, 아래).

### 새로 드러난 결함 2건 (같은 날 수정)

1. **빈 원본 대조를 완료로 받았다.**
   - source-2는 110초 만에 「Incomplete independent review」를 냈다. 이전 회차는 7–28분이었다.
   - check_file도 생성기도 이것을 정상 완료로 기록했다. 「원본 대조를 생략하면 검수 완료로 처리하지 않는다」와 어긋난다.
   - 수정: 계약 `generation_v2.require_judgment`.
     - 문항 판정이 전부 doubt이고, 방향·관계·목표 점검이 전부 unknown이며, direction_evidence가 비면 거절한다.
     - 판정이 하나라도 있으면 지금처럼 받는다. doubt·unknown 자체는 계속 허용한다.
   - 같은 세션에 한 번 되돌린다. 그래도 같으면 그 회차는 실패로 남고 정답 검수로 넘어가지 않는다.
2. **모델이 검사 명령을 실행할 수 없었다.**
   - task.md의 `.venv\Scripts\python.exe`(uv 실행기)와 그 바탕 python(`AppData\Roaming\uv`)은 샌드박스 사용자(CodexSandboxUsers)에게 실행 권한이 없다.
   - 또 uv 실행기가 러너 환경에 넣은 `PYTHONHOME`이 Codex와 모델 셸로 그대로 넘어갔다. 그래서 실행 가능한 python도 샌드박스 안에서 `No module named 'encodings'`로 죽었다.
   - 이날 세션 대부분이 「uv trampoline … permission denied」를 만났다. 대개는 돌아갔지만 source-2는 거기서 검토를 포기했다.
   - 수정:
     - `studyez_llm.codex.child_env`: uv 실행기 자신의 `PYTHONHOME`만 빼고 Codex를 띄운다.
     - `root_native_json.sandbox_python`: 모델 없이 `codex sandbox`로 후보를 한 번 시험하고, 샌드박스에서 실제로 뜨는 것을 task.md에 적는다.
       - 이 기계에서는 anaconda3이 골라졌고, 시험은 4초 걸렸다.
       - 검사 파일은 이 프로세스의 패키지 경로를 앞에 둔다.
       - 뜨는 것이 없으면 「다른 python을 찾지 말고 검토를 줄이지 말라. 호스트가 같은 검사를 돌려 한 번 되돌린다」고 적는다.
   - 샌드박스 폴더 권한(보안 설정)은 바꾸지 않았다.
- 실제 확인:
  - generation-4 source-2의 보관된 검사 파일이 샌드박스 안 anaconda로 1.7초에 돌았다(수정 전 기준으로는 빈 판정이 통과).
  - 감염병리1 공개 실행(26110803 generation-3)은 새 계약에서도 `validate_result`·`validate_all` 통과, 원본 대조 회차 모두 판정 있음.
- 검사:
  - 새 계약 4개, 러너 3개. 빈 판정 거절과 되돌린 뒤 실패는 수정 전 실패.
  - 루트 2,192 통과(desktop_control 제외, master에서도 실패), 서버 root 27개 통과.

### 아직 정하지 않은 것

- **context 충돌이 매 회차 새로 나온다.** 이전 지적만 다시 확인할지, 지금처럼 매번 전체를 볼지 정해야 한다.
  지금 방식이면 결함 2건을 고친 뒤에도 같은 이유로 멈출 수 있다.
- 위의 context `unknown`·초기 교정 예산·판정 범위 결정도 그대로 남아 있다.

## 후속: 이어 하기와 맥락 검사 (2026-11-09 사용자 「한번에 가자 … 중간 성공한 부분까지는 저장되게 해서 안된 부분부터 하자」)

### 왜 매번 처음부터였나

- 실행 지문(`identity`)에 생성기·계약·프롬프트 코드 전체의 해시가 들어간다. 그래서 한 줄을 고쳐도 같은 폴더를 이어 쓸 수 없었다.
- 그 결과 generation-1~4가 고칠 때마다 새 폴더에서 처음부터 40~60분씩 돌았다.
- 네 번 중 두 번(3·4)은 같은 곳에서 멈췄다. 맥락 검사가 충돌 기록의 누락·쪽수 오류를 conflict로 내면 그 회차 정답 검수가 통째로 빠졌다.

### 맥락 검사: 오염만 막는다 (clinical-context/2, 사용자 선택 「오염만 막기」)

- 맥락 검사가 `clinical_context_problem`을 함께 적는다.
  - `contamination`: 과거 검수 판정·검수자·수정 차수·중요도·저작 이력이 섞임. 정답 검수를 막는다(지금과 같다).
  - `incomplete`: 오염은 없고 충돌 사실이 빠졌거나 출처·쪽수가 틀림. 정답 검수는 진행하고, 「임상 충돌 정리 보완(정답 검수는 진행)」이라는 question_fix 사유로 다음 보완에 넘긴다.
  - `none`: consistent 또는 unknown. unknown은 정답 검수를 막지 않고, 보완 사유도 아니다.
- 마지막 회차의 맥락 검사가 incomplete여도 결과를 만들 수 있다. 오염이면 지금처럼 결과를 만들지 않는다.
- 이 칸이 없는 옛 기록은 옛 규칙으로 읽는다. 감염병리1 공개 결과의 재검증에는 영향이 없다.
- 원본 대조 검토자의 `clinical_context_status`(문항·충돌 보존 확인)는 바꾸지 않았다. 실제로 검토한 회차는 모두 consistent였다.

### 이어 하기 (stage-resume/1, `--resume <이유>`)

- 사람이 이유를 적어 명시할 때만 돈다. 없으면 지금처럼 「자동 재실행하지 않습니다」로 멈춘다.
- 완료된 단계는 입력이 같고, 현재 수용 검사를 다시 돌려 같은 결과가 나오면 모델 호출 없이 그대로 쓴다.
- 실패·중단 단계, 입력이 달라진 단계, 현재 검사를 통과하지 못하는 단계만 `.resume-<k>/`에 옮겨 보관하고 다시 돌린다. 지우지 않는다.
  - 옛 회차 결정 파일(`repair-decision-*`)과 재개 전 ledger도 같은 폴더에 남긴다.
- 회차 번호가 고정이라 회차를 늘리지 않는다. 보완 상한 3회도 초기화하지 않는다.
- 결과 계약(`validate_stage_resumes`)이 재개 기록을 검사한다. 버린 단계는 이전 ledger의 단계여야 하고, 남긴 단계는 바뀌지 않아야 한다.
- 거절하는 경우: 완료된 실행, 다른 복구 기록(형식·그림·저작·정답 재시도·중요도·런타임 재결합)이 있는 실행, 병렬 저작, 다른 packet.
- 파일럿: `REASON=… GEN_DIR=generation-4 bash docs/changes/2026-11-09-main-quiz-second-lecture/run-all.sh resume`.

### 사슬알균 generation-4 모의 재개 (사본, 모델 호출 없음)

- 정규화·출제는 그대로 쓰고, 처음 다시 부르는 단계는 맥락 검사 0회차였다. 옛 두 칸 형식이라 현재 검사를 통과하지 못하기 때문이다.
- 이후 순서는 실제 결과에 따라 정해진다. 예상은 다음과 같다.
  - 원본 대조 0·1과 정답 검수 0은 입력이 같아서 그대로 쓴다.
  - 맥락 검사 1·2를 다시 돌린다. incomplete로 나오면 정답 검수 1이 돈다.
  - 그 결과가 바뀌면 보완 2, 맥락 검사 2, 원본 대조 2, 정답 검수 2를 이어서 돌린다.

### 검사

- 새 검사:
  - 맥락 검사 3개: incomplete면 매 회차 정답 검수가 돌고 보완 사유가 됨 · unknown은 막지 않음 · 상태와 종류의 일치, 옛 기록은 옛 규칙.
  - 재개 4개: 실패 단계만 다시 돎 · 코드가 바뀐 뒤 완료 단계를 모델 없이 재사용 · 현재 검사를 통과 못 한 단계만 다시 돎 · 완료·다른 복구 실행 거절.
- 디렉터리별 검사는 모두 통과: runner 731, contracts+quizbank+runner 1,548, 새 재개 파일을 뺀 전체 2,195.
- 전체를 한 프로세스로 돌리면 3번 중 3번, `root_chunked_tasks` 검사의 작업 스레드에서 인터프리터가 죽었다(Windows access violation, 가비지 수집 중).
  - 같은 조합을 좁혀 돌리거나 재개 테스트를 둘씩 나누면 통과한다. 바꾸기 전 master는 통과했다.
  - 특정 테스트가 아니라 가비지 수집 시점의 문제로 본다. 앞에서 만든 C 확장 객체(PDF 라이브러리 등)가 작업 스레드 안에서 해제됐다.
  - 운영 실행도 원본 대조 ‖ 정답 검수를 스레드로 돌리므로 같은 위험이 있다.
  - 수정: 스레드를 띄우기 직전에 호출한 스레드에서 `gc.collect()`를 한다(`connection_generate_v2`의 원본 대조 ‖ 정답 검수, `root_chunked_tasks`).
  - 수정 뒤 전체 2,199 통과(desktop_control 제외), 충돌 0. 서버 root 27 통과, `map_numbers --check` 정상.

## generation-4 이어 하기 결과 (2026-11-09 13:35–14:00, PR #56 코드)

- 처음으로 `result.json`이 나왔다. `validate_result`·`validate_all` 통과.
- 다시 돈 단계: context-0·1·2, medical-1·2, repair-2, source-2. 나머지(정규화·출제·source-0·1·medical-0·repair-1)는 모델 없이 재사용했다.
- 맥락 검사 1·2는 둘 다 incomplete였다. 정답 검수는 막히지 않았다.
- 결과:
  - 문항 133, 학습 과제 82.
  - 정답 검수: ok 120 · doubt 11 · wrong 2(Q042 괴사근막염 정의, Q097 「폐 실질 질환」에 수막염).
  - 원본 대조: ok 127 · doubt 5 · wrong 1.
  - 학습 목표 119 중 ready 63 · partial 4 · blocked 52. 고치지 못한 지적 62건(보완 3/3).
- 막힌 목표:
  - 일반 목표(D)는 89개 중 63개가 준비됐다(71%). 감염병리1은 93개 중 56개(60%)였다.
  - **연결 목표(DR, role branch) 30개는 전부 막혔다.** 감염병리1에는 연결 목표가 없었다.
  - 원인: 원본 대조가 연결 목표의 중요도를 0·2회차에 unknown으로 남겼다(1회차는 consistent 19 · conflict 11).
  - 이유는 30개 모두 같다: 「개별 포인트 근거는 있지만 연결 전체의 중요도를 직접 지지하는지는 별개다. 자동 전이를 승인하지 않는다.」
  - 처음 보고에서 이를 「검토 누락」이라고 했는데 틀렸다. 검토자는 일부러 판정을 보류했다.
- 검토 페이지(비공개): https://claude.ai/artifact/6iPR4QUkTDES3YEvtdtpJF
- 운영 반입·학생 공개는 하지 않았다(사용자 「아직 말고 내용부터」).

## 후속: 연결 목표의 중요도 (2026-11-09 사용자 「계산값 쓰고 내용만 검토」)

- 원본 대조 지시문(`source-v2.md`):
  - 연결 목표(role branch/root)의 targetImportance는 importance-basis/1이 이어진 포인트 근거에서 계산한 값이다. 전이 자체는 승인 대상이 아니다.
  - target_checks는 이어진 포인트 근거가 원본과 맞는지, 연결 내용이 원본에 있는지만 판정한다.
  - 「연결 전체의 중요도를 직접 지지하는지 확인할 수 없다」만으로 unknown·conflict를 내지 않는다. 내용이 원본과 다르면 conflict다.
- `--rerun <단계>`(`--resume`과 함께): 지정한 완료 단계를 다시 돌린다. 입력이 바뀐 후속 단계만 따라 돈다.
  - 완료된 실행은 이때만 연다. 기존 `result.json`은 `.resume-<k>/`로 옮긴다(지우지 않는다).
  - 사슬알균은 지시문이 바뀐 마지막 원본 대조(source-2)만 다시 돌린다. 지시문은 단계 입력에 들어가지 않아 자동으로는 다시 돌지 않는다.
  - 검토를 반복해 의심을 줄이려는 것이 아니다. 판정 기준이 바뀐 단계 하나를 다시 판정한다. 보완 횟수는 늘지 않는다.
- 사본 모의 재개(모델 호출 없음): source-2만 다시 부르고 나머지는 재사용한다.
- 검사: 재개 검사 1개 추가(지정 단계만 다시 돎 · 완료 단계만 지정 가능)와 완료 실행 재개 확인.
- 루트 2,198 통과, 충돌 0. 오류 2개는 상태 창 검사의 Tk 초기화(`tcl_findLibrary`)였고 따로 돌리면 통과한다. `map_numbers --check` 정상.

### source-2 재판정 1차 (14:52): 또 검토 포기

- 새 지시문으로 돌린 source-2가 157초 만에 「부분 검수」로 끝났다. 133문항 중 131개 doubt, 판정한 문항은 Q002·Q003뿐이다.
  - 맥락 판정이 unknown이라 결과 조립에서 거절됐다(`final clinical input separation not verified`). 결과 파일은 없다.
  - 직전 결과는 `generation-4/.resume-2/result.json`에 보관돼 있다.
- 이 세션은 7번째 호출에서 미완료 초안을 만들었다. 빈 판정 규칙(`require_judgment`)에 걸리자 2문항만 판정을 채워 그 규칙을 넘겼다.

## 진단: 원본 대조는 왜 포기하나 (2026-11-09 사용자 「왜 저런 결과가 나오는지 먼저 진단해볼까?」)

지금까지 돈 원본 대조 19번(26110801~26110901)의 Codex 세션 기록을 모두 비교했다.

| | 횟수 | 실제로 받은 이미지 | 시간 | doubt |
|---|---|---|---|---|
| 완료 | 13 | 53~76장(사슬알균 원본 46쪽 + 문항 그림 7) | 294~1,690초 | 대부분 2~19% |
| 포기 | 6 | 0~8장 | 110~175초 | 89~100% |

- 포기한 6번: 감염병리1 26110802 source-1, 사슬 gen-2 source-0, gen-3 source-1·2, gen-4 source-2 두 번.
- 갈림길은 모델이 원본 쪽 이미지를 한꺼번에 열기로 하느냐다.
  - 완료한 세션은 초반에 스크립트로 쪽 이미지를 모두 연다.
  - 포기한 세션은 이미지를 거의 열지 않고 「원본 46쪽을 다 대조하지 못했다」는 미완료 초안부터 쓴다. 6번의 요약이 모두 같은 말이다.
- python 실패, 잘린 입력 출력, 이름만 쓴 `python`의 PATH 오류는 완료한 세션에도 똑같이 있었다. 갈린 원인이 아니다.
- 지시문이 「모든 원본 쪽과 PNG를 읽어라」와 「확인할 수 없으면 unknown」을 함께 주고, 이미지를 어떻게 열지는 모델에게 맡긴다. 그래서 세 번에 한 번꼴로 일을 시작하기 전에 unknown 쪽을 고른 것으로 본다.
- 맥락 검사의 unknown(gen-3 context-1: 「나머지 PNG를 직접 대조한 근거가 없다」)도 같은 원인으로 본다.
- 비율로 거르는 규칙은 넣지 않았다. 최근 세션은 빈 판정 규칙을 판정 몇 개로 넘겼으니, 비율 선도 같은 방식으로 넘을 수 있다.

## 수정: 검토 단계에 원본 이미지를 처음부터 붙인다 (사용자 「이미지 처음부터 붙이기」)

- `runner/root_native_json.review_images`: 원본 대조(source-n)와 맥락 검사(context-n)의 첫 메시지에 붙인다.
  - 원본 쪽 PNG(`material/S*-NNNN.png`, 원본·쪽 순서)를 먼저, 문항 그림(stimulus)을 그다음에 붙인다.
  - 첫 메시지에 파일 이름과 순서를 적는다. 영수증 증명(`attachedImages`)에 파일과 SHA256을 남긴다.
- 모델이 받는 것은 work/material의 같은 파일이다. 사슬알균은 53장, 13MB다.
- 정규화·출제·보완 단계는 바꾸지 않았다.
- 검사: 새 1개(두 검토 단계에 쪽+그림이 순서대로 같은 bytes로 붙고 증명에 남음, 다른 단계는 없음). 루트 2,201 통과.

### source-2 재판정 2차 (15:31, 이미지 첨부): 실제 검토, 그러나 저작용 칸 때문에 거절

- 이미지 53장이 첫 메시지에 실제로 붙었다(세션 기록 확인). 328초 동안 검토했고, 결과는 ok 124 · doubt 8 · wrong 1, 연결 목표 30개 모두 consistent였다.
- 그러나 임상 정리를 conflict로 판정해 결과 조립에서 거절됐다.
  - 이유는 Q106·Q036·Q037·Q070 등의 `exam_rationale`에 「EXT: 제공된 의학 검수에 따른 교정」, 「필수 누락 보완」이 남았다는 것이다.
  - `exam_rationale`은 정답 검수 입력(`medical_input`)에 들어가지 않는다. 웹에서도 관리자 카드 검토 화면에만 나온다.
- 사용자 결정 「통과시키기」(2026-11-09):
  - 오염 판정은 정답 검수자가 읽는 칸(문제·정답·정답 단위·선지·선지 해설·해설·clinical_conflicts)만 본다.
  - 저작용 칸의 이력은 question_fix로 적는다. `source-v2.md`·`context-v2.md`에 반영했다.

### source-2 재판정 3차 (16:00) — 결과

- 440초 동안 검토했다. ok 124 · doubt 7 · wrong 2이고, 임상 정리는 consistent다. exam_rationale 이력은 question_fix로 분리됐다.
- `result.json` 생성, `validate_result`·`validate_all` 통과.

| | 14:00 판 | 16:06 판 |
|---|---|---|
| 학습 과제 | 82 | **96** |
| 준비된 목표 | 63 / 119 | **79** / 119 (partial 6, blocked 34) |
| 연결 목표 준비 | 0 / 30 | **23** / 30 |
| 일반 목표 준비 | 63 / 89 | 56 / 89 |
| 정답 검수 | ok 120 · doubt 11 · wrong 2 | 같음(재사용) |
| 원본 대조 | ok 127 · doubt 5 · wrong 1 | ok 124 · doubt 7 · wrong 2 |
| 고치지 못한 지적 | 62 | 67 (required_gap 26 · question_fix 25 · map_fix 16) |

- 남은 막힘 40개의 가장 큰 원인은 목표 전체를 답으로 묻는 문항이 없는 것이다(26).
- 정답 오류는 Q042·Q097이고, 원본 대조 wrong에 Q089가 더해졌다. 보완 3/3이라 그대로 남는다.
- 보관: 14:00 판 결과는 `generation-4/.resume-2/result.json`, 14:52·15:31 source-2는 각각 `.resume-3/`·`.resume-4/`에 있다.
- 검토 페이지를 갱신했다(Version 2): https://claude.ai/artifact/6iPR4QUkTDES3YEvtdtpJF
- 운영 반입·학생 공개는 하지 않았다.

## 운영 반입 (2026-11-09 사용자 「반입해줘」)

- `publication.py`는 감염병리1의 반입 스크립트를 이 강의에 맞게 옮긴 것이다. 순서는 preflight(읽기만) → 배포 확인 → 원본 스냅숏 → 등록 → 전후 대조다.
  - 바꾼 점: 처음 반입하는 강의라 공개 범위가 관리자 시범(`['runner']`)으로 생기는지 확인한다. 다른 강의의 Main-Quiz 판 수·설정이 그대로인지도 대조한다.
- preflight 결과: 강의는 있고, Main-Quiz 판·설정·이벤트·세션은 0개였다. 다른 강의는 판 3개, 설정 1개였다.
- 운영 API 2a3ad0b2(PR #57) 배포를 확인한 뒤 반입했다.
  - generationId `3d80ffb0caaf178968f5e0203507237b`, revision `map-tree-26110901`, 과제 96.
  - 공개 범위: 관리자 시범 `allowed_users=['runner']`, enabled. **학생 공개는 하지 않았다.**
  - publication 이벤트 0 → 1건. 다른 강의 Main-Quiz, Quiz Bank, 학습 상태, 세션은 그대로다(스크립트 전후 대조).
- 기록: `runs/_e2e/26110901/publication/{preflight,published}.json`.

## 학생 공개 (2026-11-09 사용자 「학생 공개」)

- `open_to_students.py`가 관리자 publication 경로(`routes/root_learning.publish`)를 그대로 호출했다. 감염병리1 공개 때와 같은 방식이다.
- 바뀐 것은 `allowed_users`뿐이다(`['runner']` → `[]` 전체). revision `map-tree-26110901`과 enabled는 그대로다.
- 이 강의의 이벤트는 3 → 4건이다(publication 1건 추가). 다른 강의의 Main-Quiz 설정(1개)은 그대로다.
- 기록: `runs/_e2e/26110901/publication/open-to-students.json`. 운영 API 2a3ad0b2.
