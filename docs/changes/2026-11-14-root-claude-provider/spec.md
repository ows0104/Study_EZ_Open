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
   - `resume`은 같은 세션 이어 하기(`--resume <session_id>`)이며 사용량은 Codex처럼 이전 누적값을 빼서 이번 호출분만 센다.
4. **실패 구분.** 종료 코드·`is_error`·빈 응답은 `SessionError`. 응답이 안전상 거절(stop reason `refusal` 또는 거절 오류문)이면
   `ContentRestricted`로 올려 기존 `classify_error` → `model_content_restricted`, `automaticRetry=False`로 보류한다.
   사용 한도·요금 한도 메시지는 기존 사용량 한도 처리로 간다. 네트워크 끊김 판정(`network_failure`)도 같은 기준을 쓴다.
5. **동시 실행·중복 차단.** `execution.exclusive`(같은 요청 차단)와 `slot`을 그대로 쓴다. Claude 동시 실행 수는
   `STUDYEZ_CLAUDE_SLOTS`(기본 2)로 Codex 자리와 따로 센다.
6. **원장의 정직한 기록.**
   - native 영수증 proof의 `model`은 실제 모델, provider 응답은 `provider.json`에 그대로 둔다(세션 ID는 Claude 세션 ID).
   - `validate_stage`는 그 단계를 완료할 때 원장에 적힌 모델로 확인한다(단계 entry의 `model`, 없으면 지금 모델 — 기존 단계와 호환).
   - 생성기 원장 identity는 지금처럼 모델을 포함한다. 모델이 바뀌면 관리자의 재개 이유가 있을 때만 이어 가고, 재개 행에
     `modelBefore`·`model`을 남긴다(기존 `identityBefore`와 같은 자리).
   - 결과 manifest의 `model`은 생성 단계 모델(Claude)이다. 앞 단계(front)는 단계별 기록에 이미 Codex 모델이 남아 있다.
7. **강의별 지정.** `runs/model-overrides.json`
   ```json
   {"version": 1, "generations": {"<generationId>": {"model": "claude-opus-5-5", "reason": "…", "approval": "사용자 발언 원문", "at": "ISO 시각"}}}
   ```
   러너(agent)는 Main-Quiz 일감(`rootGenerationId` 있음)을 실행할 때 이 파일에 그 ID가 있으면 `--model <model>`을 붙인다.
   파일이 없거나 ID가 없으면 지금 명령과 같다. 파일 형식이 틀리면 그 일감을 실행하지 않고 보류 사유로 보고한다(기본 모델로 조용히 넘어가지 않는다).
   러너 로그에 「모델 지정: claude-opus-5-5 (runs/model-overrides.json)」을 한 줄 남긴다.
8. **복구 도구 거절.** `root_chunked_*`·`root_plan_repair`·`root_session_resume`·`root_authoring_resume`·`root_task_supplement`·
   `root_quiz_curation`은 Claude 모델이면 「이 복구 도구는 Codex 기록 전용」으로 시작 전에 멈춘다.

## 책임·입출력 계약·오류 상태

| 책임 | 위치 |
|---|---|
| Claude CLI 명령·출력 해석·사용량 | 새 `studyez_llm/claude.py` |
| 모델 이름 → 공급자 선택, 공통 `run`/`model_name` | 새 `studyez_llm/models.py` |
| 동시 실행 자리(공급자별) | `studyez_llm/execution.py` |
| 생성 단계 호출·영수증·단계 검증 | `runner/root_native_json.py` |
| 앞 단계 호출 | `runner/root_front.py` |
| 생성기 원장 identity·재개 행·manifest model | `quizbank/connection_generate.py`, `connection_generate_v3.py`, `connection_generate_v4.py` |
| 게시 뒤 근거 보강·선지 | `quizbank/root_evidence.py`, `quizbank/root_choices.py`(이미 `--model`을 받는다. 공통 선택기로만 바꾼다) |
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
