# root-generation/3: 판정 값이 강의를 멈추지 않게 — 설계

배경과 진단은 [intent.md](intent.md)에 있다. 바탕 설계는 [root-generation/3 spec](../2026-11-10-root-generation-3/spec.md)이고, 이 문서는 그 R5·R5a·R6과 오류 상태를 바꾼다.

## 원칙 P7 (모든 단계에 적용)

**판정 값은 강의를 멈추지 않는다. 그 값이 가리킨 목표·문항·충돌 기록에만 미친다.**

- 강의를 멈추는 것은 「단계가 받아들일 출력까지 가지 못한 것」뿐이다. 그 단계는 실패로 기록되고, 이어 하기가 그 단계를 다시 돈다.
- 완료된 단계의 값을 이유로 멈추는 곳은 하나만 남긴다: 조립해 보니 과제가 하나도 없을 때. 이때는 목표별 이유를 적고 의학 검토 전에 멈춘다.
- 한 단계가 아무것도 판정하지 않은 것(전부 unknown)은 값이 아니라 미수행이다. 새 세션으로 한 번 다시 돌고(review-retry/1), 또 그러면 실패로 기록한다. 커버·문항 검토에 더해 지도 확인과 임상 정리에도 적용한다.

## 요구사항과 수용 기준

### R5a′. 임상 정리 — 충돌 기록마다 판정 `v3-context-0`, `v3-context-1`

/2 `context` 단계와 `context-v2.md`를 /3에서 쓰지 않는다. 새 프롬프트는 `content/prompts/learning-links/v3/context.md`다.

- **입력** `generation_v3.context_input`
  - `conflicts`: 충돌 기록마다 원본 충돌 기록, 의학 검토에 보낼 사실(facts), 인용 문항 ID
  - `questions`: 의학 검토자가 읽는 칸(발문·정답·답 단위·선지·해설·선지 해설)
    - 전체 판정은 모든 문항을, 보완 뒤 재판정은 고친 문항과 재판정 대상 충돌의 인용 문항만 넣는다.
  - `pages`: 인용 문항이 인용한 쪽
- **출력** `CONTEXT_OUTPUT`
  - `conflicts`: 기록마다 한 줄. `status`는 consistent · contamination · incomplete · unknown
  - `questions`: 글에 검수 이력이 섞인 문항만
  - `unrecorded`: 읽다가 발견한, 어느 기록에도 없는 원본 충돌(한 문장씩)
- **경계를 프롬프트에 적는다.**
  - 지금 문항이 쓰는 답을 적은 문장(「현재 정답은 A다」)은 facts에 있어야 하는 내용이고 검수 이력이 아니다.
  - 원본 안의 정정(교수 문의 정정, 필기자 수정, 족보 정답 토의)은 원본 사실이다.
  - 검수 이력은 과거 검수 판정, 검수자 판단, 수정 차수, 중요도, 내부 ID, 「보완」·「지적」 경위다.
- **처리**

| 판정 | 처리 |
|---|---|
| 기록이 consistent | 그 사실을 의학 검토에 보낸다 |
| 기록이 그 밖(contamination·incomplete·unknown) | 인용 문항을 고치기 한 번(`v3-fix-context-0`)에 넣는다. 문항별 2번 상한을 같이 쓴다. 그 뒤 그 기록만 다시 판정한다(`v3-context-1`) |
| 다시 판정해도 consistent가 아님, 또는 고칠 횟수가 남은 인용 문항이 없음 | 그 기록의 사실을 의학 검토에 보내지 않는다. 문항과 과제는 그대로 둔다. manifest `clinicalContext`에 남는다 |
| 문항 글에 검수 이력 | 같은 고치기 한 번에 넣고 다시 본다. 남으면 기록만 한다 |
| `unrecorded` | 기록만 한다. 어느 문항도 막지 않는다 |
| 기록 전부 unknown | 미수행이다(P7). 새 세션으로 한 번 다시 |

- **결정 (이 작업에서 정함, 사용자가 뒤집을 수 있다)**: 일치가 아닌 충돌을 인용한 문항도 과제에 남긴다.
  - 근거: 임상 정리가 지키는 것은 의학 검토자가 과거 판정을 보지 않는 것이다. 사실을 보내지 않으면 그 목적은 지켜진다.
  - 의학 검토는 medical-final/1에서 과제를 빼지 않는다(사용자 2026-11-09). 그 문항은 문항 검토(원본 대조)를 이미 거쳤다.
  - 반대로 정하려면 `generation_v3.context_open`이 낸 충돌의 인용 문항을 `offGoalQuestions`처럼 과제에서 빼면 된다.
- **/2 조립의 임상 정리 칸**은 코드가 만든다(`context_summary`). 의학 검토에 간 사실은 모두 일치 판정을 받은 것이므로 상태는 consistent이고, 이유에 보내지 않은 충돌과 이력이 남은 문항을 적는다.
- **수용 기준**
  - 가짜 모델이 한 기록을 두 번 다 contamination·incomplete로 판정해도 결과가 나오고, 과제는 일치 판정일 때와 같다.
  - 그때 의학 검토 입력에 그 기록의 사실이 없다.
  - 재판정 입력에는 보완이 건드린 기록만 있다.
  - 결과 검증이 `contextJudgments`(단계 출력)에서 `clinicalContext`를 다시 합쳐 대조한다.

### R5′. 의학 검토 — 문항 하나가 단계를 멈추지 않는다

- 검수 이력 표현(/2 `medical_input`이 입력 전체를 거절하는 정규식)이 있는 문항
  - 4단계 코드 검사 지적으로 넣어 고치기 대상이 된다.
  - 상한 뒤에도 남으면 의학 검토에 보내지 않고 기록한다.
- 한 묶음이 빠뜨린 판정은 그 문항들만 한 번 더 묻는다. 그래도 없으면 기록한다.
- 기록 방식: 의학 검토 줄은 `doubt`(검토의 「판단 보류」)이고 note가 「의학 검토 판정 없음(코드 기록): …」으로 시작한다. manifest `medicalUnreviewed`에 문항과 이유가 있다.
- 수용 기준: 판정을 한 줄 빠뜨리는 가짜 모델로 결과가 나오고, 그 문항이 `medicalUnreviewed`에 있다.

### R6′. 조립은 의학 검토 전에 돈다

- 순서: … → 임상 정리 → **조립** → 의학 검토 → 결과 기록.
- 조립이 거절하는 것은 의학 검토 호출 전에 드러난다.
- `generation_v3.readiness`: 목표마다 과제가 됐는지와 안 된 이유를 조립이 쓴 판정에서 계산한다. 새 판정을 만들지 않는다.

| 이유 | 뜻 |
|---|---|
| no-question | 목표 전체를 답으로 묻는 문항이 없다 |
| coverage-unknown | 커버 판정이 unknown이다 |
| question-not-ok | 커버 문항이 모두 문항 검토에서 doubt·wrong이다 |
| visual | 그림 판정이 통과가 아니다 |
| prerequisite-check | 커버 문항의 선행 판정이 supported가 아니다 |
| relation · target · scope | 지도 확인의 관계·중요도 근거·범위 판정이 통과가 아니다 |
| no-point | 목표에 이어진 포인트가 없다 |
| dependency | 자기 판정은 통과했는데 선행 문항·선행 목표가 준비되지 않았다 |

- 실행 폴더에 `readiness.json`을 쓰고 로그에 한 줄로 센다. manifest `readiness`에 넣고 결과 검증이 다시 계산한다.
- 과제가 0개면 여기서 멈춘다. 메시지에 이유별 개수가 있다.
- 커버 판정이 missing·unknown인 목표의 증거는 증거로만 남고 관계를 시험한 것으로 세지 않는다. 임의 판정 검사가 찾은 모순(「준비 안 됨」 목표에 과제가 생김)이다.

### R7. 모델이 쓴 파일

- 수신 검사 `runner/root_native_json.check_file`은 글자가 깨진 값을 돌려보낸다(`garbled`).
  - U+FFFD가 있다.
  - `?`가 세 개 이상 이어진다.
  - `?`가 여덟 개 이상이고 글의 10분의 1 이상이다.
- 단계 안에서 모델이 스스로 돌리는 검사와 러너의 후속 메시지가 같은 함수를 쓴다.
- /3 전송 지시에 적는다: UTF-8 `.py` 파일로 저장해 실행하고, 한글을 셸 파이프·here-string·명령줄로 넘기지 않는다.

### R8. 그 밖

- 실행 폴더 경로가 길어 단계 폴더의 파일이 Windows 한도(259자)를 넘으면 러너의 생성기 진입점(`runner.root_native_json.main`)이 모델 호출 전에 멈춘다. 사본 재생에서 늦은 단계의 폴더 복사가 실패했다.
- 범위 밖 문항을 뺄 때 다른 문항의 선행 목록에서도 뺀다.
- 이어 하기는 이 코드가 더 만들지 않는 단계 이름(`context-0`, `context-1`)을 다른 대체 단계처럼 `.resume-<k>/`로 옮긴다.

## 책임·입출력 계약·오류 상태

- 계약: `studyez_contracts/roots/generation_v3.py`
  - 새 함수: `context_input`, `check_context`, `context_merge`, `context_open`, `context_sent`, `context_summary`, `context_repair_targets`, `context_findings`, `history_marked`, `medical_parts`, `unreviewed_row`, `readiness`
  - `validate_result`: 새 manifest 칸 `contextJudgments`·`medicalUnreviewed`·`readiness`를 요구한다.
- 생성기: `quizbank/connection_generate_v3.py`. 러너: `runner/root_native_json.py`.
- 멈추는 경우 (전부)

| 경우 | 종류 | 이어 하기 |
|---|---|---|
| packet·원본·ledger 불일치, 경로 길이 | 입력 | 고친 뒤 |
| 정리(normalize)·지도 구조 교정 실패 | 단계 실패 | 그 단계부터 |
| 단계 출력이 수신 검사를 한 번 돌려받고도 통과 못 함 | 단계 실패 | 그 단계부터 |
| 한 단계가 두 번 연속 아무것도 판정하지 않음 | 단계 실패 | 그 단계부터 |
| 콘텐츠 거절 | 보류(/2와 같다) | /2와 같다 |
| 과제 0개 | 값 | 판정이 바뀌어야 한다. `readiness.json`이 이유를 말한다 |

## 호환성과 데이터 보존

- /2: 계약·프롬프트·결과 검증을 바꾸지 않는다. `medical_input`의 정규식을 `HISTORY_MARKERS`로 이름만 붙였다.
- /3 결과: 서버에 반입된 /3 결과는 아직 없다(261102_02는 422로 거절됐다). 새 manifest 칸이 없는 옛 /3 결과는 검증을 통과하지 못한다.
- 261102_02 실행 폴더: 이어 하면 완료 단계는 그대로 쓰고 `context-0` 기록은 `.resume-<k>/`로 간다. `v3-context-0`과 의학 검토만 새로 부른다.
- 서버: `studyez_contracts`를 같이 쓰므로 master 병합 배포로 같은 검증을 갖는다. DB 변경은 없다.
- 러너: 새 코드를 쓰려면 설치본을 다시 깔아야 한다.
