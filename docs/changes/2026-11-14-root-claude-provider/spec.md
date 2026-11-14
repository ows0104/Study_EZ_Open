# Main-Quiz 강의별 Claude 출제 경로 — 설계

## 요구사항과 수용 기준

1. **공급자 선택은 모델 이름으로만 한다.** `gpt-…`는 Codex, `claude-…`는 Claude Code CLI. 다른 이름은 실행 전에 거절한다.
   기본값(`STUDYEZ_MODEL` 또는 `gpt-6.1-sol`)은 바뀌지 않는다.
2. **같은 호출 계약.** 새 `studyez_llm.claude.run()`은 `codex.run()`과 인자·반환 형식이 같다.
   반환: `text`, `session_id`, `turns`, `usage`(input/output/cache_read/cache_creation), `session_usage`, `cost_usd`,
   `duration_ms`, `models`, `provider='claude'`, `warnings`.
3. **같은 작업 조건.**
   - 작업 폴더: 단계 work 폴더 하나(cwd). 다른 폴더를 열지 않는다(`--add-dir` 없음, `writable`만 허용).
   - 도구: blind=False → Read·Write·Edit·Glob·Grep·Bash만. 웹 검색·웹 가져오기·MCP·하위 에이전트는 끈다. blind=True → 도구 없음.
   - 사용자·프로젝트 설정, CLAUDE.md, 훅, 플러그인, 기억을 싣지 않는다(최소 설정 모드 + 빈 MCP 설정).
   - `system`은 시스템 프롬프트로, `schema`는 구조화 출력(`--json-schema`)으로 넘긴다.
   - `images`는 첫 사용자 메시지에 이미지 블록으로 붙인다(stream-json 입력). Codex의 `--image`와 같은 바이트다.
   - 긴 `system`·`schema`(8,000자 초과)는 Windows 명령줄 한도 때문에 인자 대신 첫 메시지 앞·뒤에 그대로 싣는다.
   - 이미지가 20장 또는 20MB를 넘으면 붙이지 않고 같은 파일 경로를 알려 Read 도구로 열게 한다(일부만 붙이지 않는다).
   - `resume`은 같은 세션 이어 하기(`--resume <session_id>`). Claude의 결과 사용량은 그 호출분이므로 그대로 `usage`이고,
     `session_usage`는 이전 누적값에 더한 값이다(Codex의 누적값 차감과 같은 결과).
   - 인증은 이 PC의 Claude Code 로그인(구독)을 쓴다. 최소 설정 모드(`--bare`)는 API 키만 받으므로 `--safe-mode`를 쓴다.
4. **실패 구분.** 종료 코드·`is_error`·빈 응답은 `SessionError`. 응답이 안전상 거절(stop reason `refusal` 또는 거절 오류문)이면
   거절 표식 `[CLAUDE_CONTENT_RESTRICTED]`을 단 `SessionError`로 올려 `classify_error` → `model_content_restricted`,
   `automaticRetry=False`로 보류한다(메시지는 「Claude가 … 거절」).
   거절 표식 파일(`content-block.json`) proof에 `provider: "claude"`를 남긴다. Codex 표식은 모양을 바꾸지 않는다(없으면 codex).
   표식은 **거절한 공급자에게만** 다시 보내지 않게 막는다. 다른 공급자의 실행은 막지 않고, 관리자 재개가 그 실패 단계를
   표식과 함께 `.resume-<k>/`에 보관한다. 모델을 모르는 호출(`model=None`)은 지금처럼 모든 표식에 막힌다.
   사용 한도·요금 한도 메시지는 기존 사용량 한도 처리로 간다. 네트워크 끊김 판정(`network_failure`)도 같은 기준을 쓴다.
5. **동시 실행·중복 차단.** `execution.exclusive`(같은 요청 차단)와 `slot`을 그대로 쓴다. Claude 동시 실행 수는
   `STUDYEZ_CLAUDE_SLOTS`(기본 2)로 Codex 자리와 따로 센다.
6. **원장의 정직한 기록.**
   - native 영수증 proof의 `model`은 실제 모델, provider 응답은 `provider.json`에 그대로 둔다(세션 ID는 Claude 세션 ID).
   - `validate_stage`는 지금처럼 이번 실행 모델로 확인한다. 그래서 **생성 단계(generation/) 중 다른 모델로 완료된 단계가 있으면
     모델을 바꿔 이어 가지 못하고 검증에서 멈춘다**(조용히 섞지 않는다). 261109_02는 완료된 생성 단계가 없다(normalize 실패).
   - 생성기 원장 identity는 지금처럼 모델을 포함한다. 모델이 바뀌면 관리자의 재개 이유가 있을 때만 이어 가고, 기존 재개 행의
     `identityBefore`·`identity`가 그 전환을 기록한다.
   - 결과 manifest의 `model`은 생성 단계 모델(Claude)이다. 앞 단계(front)는 단계별 기록에 이미 Codex 모델이 남아 있다.
7. **강의별 지정.** `runs/model-overrides.json`
   ```json
   {"version": 1, "generations": {"<generationId>": {"model": "claude-opus-5-5", "reason": "…", "approval": "사용자 발언 원문", "at": "ISO 시각"}}}
   ```
   러너(agent)는 Main-Quiz 일감(`rootGenerationId` 있음)을 실행할 때 이 파일에 그 ID가 있으면 `--model <model>`을 붙인다.
   파일이 없거나 ID가 없으면 지금 명령과 같다. 파일 형식이 틀리면 그 일감을 실행하지 않고 보류 사유로 보고한다(기본 모델로 조용히 넘어가지 않는다).
   러너 로그에 「모델 지정: claude-opus-5-5 (runs/model-overrides.json)」을 한 줄 남긴다.
8. **복구 도구는 Codex 전용으로 둔다.** `root_chunked_*`·`root_plan_repair`·`root_session_resume`·`root_authoring_resume`·
   `root_task_supplement`·`root_quiz_curation`은 `--model`을 받지 않고 기본 모델(`STUDYEZ_MODEL`)만 쓴다. 강의별 지정은
   `--model`로만 전달되므로 이 도구들에 닿지 않는다. 전역 `STUDYEZ_MODEL`을 Claude로 바꾸지 않는다(문서에 명시).

## 책임·입출력 계약·오류 상태

| 책임 | 위치 |
|---|---|
| Claude CLI 명령·출력 해석·사용량 | 새 `studyez_llm/claude.py` |
| 모델 이름 → 공급자 선택 | `studyez_llm/codex.py`의 `model_name`·`provider`, `run`이 `claude-…`를 `claude.run`으로 넘긴다 |
| 동시 실행 자리(공급자별) | `studyez_llm/execution.py`(`slot(pool=…)`, `claude_slot_limit`) |
| 공급자별 거절 표식·Claude 거절 판정·검사용 Python | `runner/root_native_json.py` |
| 앞 단계·생성기·게시 뒤 근거 보강·선지 | 바꾸지 않는다. 모두 `codex.run(model=…)`·`codex.model_name(model)`을 이미 거치므로 같은 분기를 탄다 |
| 강의별 지정 읽기·명령 조립 | `runner/agent.py` + 새 `runner/model_overrides.py` |

오류 상태는 새로 만들지 않는다. 거절은 `model_content_restricted` 보류, 실행 실패는 기존 단계 실패, 지정 파일 오류는 일감 보류다.

## 호환성과 데이터 보존

- 지정이 없는 모든 경로는 명령 인자·프롬프트·원장 내용이 바이트 단위로 같아야 한다(회귀 검사로 확인).
  다만 `studyez_llm` 코드 해시가 identity에 들어가므로, 배포 뒤 진행 중인 Codex 판의 identity도 바뀐다. 이것은 매 러너 배포 때와 같은 기존 동작이다.
- 261109_02의 기존 산출물은 그대로 둔다. 실패한 normalize 기록은 재개 때 기존 규칙대로 `.resume-<k>/`에 보관된다.
  `provider-blocks/`의 거절 증거와 이번 조사 보고서도 보존한다.
- 앞 단계(front) 완료분(Codex)은 재사용한다. 앞 단계 재사용 판정은 모델을 보지 않는다(입력·출력 지문만 본다).
- 서버 계약은 `manifest.model`이 비어 있지 않은 문자열이면 받는다. 서버 변경은 없다.
- 학습 기록·공개 범위·문항 ID 정책은 바뀌지 않는다. 261109_02는 아직 게시된 판이 없어 판 교체가 아니다.
