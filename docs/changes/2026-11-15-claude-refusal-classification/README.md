# Claude 안전 분류기 거절을 콘텐츠 제한으로 분류

## Intent
2026-11-15 261109_02(generation `2bcdcf1f3feb4542938e66882c46875f`)를 Claude(`claude-opus-5-5`)로 출제하던 중
`v4-fix-1-1`이 두 번(`.resume-4`, `.resume-5`) 보류됐다. 원인은 Claude 안전 분류기가 탄저 두 문항의 수정 스크립트를
멈춘 것(세션 기록 `stop_reason: refusal`, `stop_details.category: bio`)인데, 원장에는
`execution_failed` / `Expecting value: line 1 column 1 (char 0)`로 남아 네트워크 문제로 읽혔다.
이 작업은 분류만 바로잡는다. 프롬프트·스키마·검수 정책·영수증 규칙은 바꾸지 않는다.

## 원인
Claude Code CLI(2.1.282)는 안전 분류기가 응답을 멈추면 그 응답을 출력에서 빼고 같은 세션을 **한 번 더** 이어 간다.
- 멈춘 응답의 도구 호출 자리에 오류 tool_result를 넣는다:
  `Interrupted: the response that made this tool call was stopped by a safety classifier …` 또는 `Not run: …`
- 시스템 알림 `<모델>'s safeguards stopped the response above · continuing once with that noted`
- 모델에게 주는 사용자 메시지(stream-json에서는 `isSynthetic`) `Your response above was stopped by a safety classifier — …`

이어 간 응답은 「다시 쓰지 말라」는 안내대로 결과 파일 없이 끝나고(가짜 영수증은 내지 않았다), result 이벤트는
`subtype: success`, `stop_reason: end_turn`이다. stream-json의 assistant 이벤트는 정상 세션에서도 `stop_reason: null`이라
(같은 CLI로 확인), `studyez_llm/claude.py`가 보던 assistant·result의 `stop_reason == "refusal"`은 이 경로에서 한 번도 보이지 않는다.
그래서 `claude.run`이 정상 완료를 돌려주고, `NativeJson.file`의 `loads(result['text'])`가 영수증 아닌 설명문에서 실패했다.

## Spec
- `studyez_llm/claude.py` `refusal_sign`: 다음 중 하나가 stream에 있으면 거절이다.
  - assistant 메시지나 result의 `stop_reason == "refusal"` 또는 `stop_details.type == "refusal"`(이전부터 보던 것 + 세부)
  - CLI가 넣는 사용자 문자열 메시지(또는 text 블록)가 `REFUSAL_NUDGE`로 시작
  - `is_error` tool_result의 내용이 CLI의 두 문구(`REFUSAL_TOOL_RESULTS`)와 **정확히** 같음
  - `system`/`informational` 알림에 `safeguards stopped the response above`
  모델이 쓴 글, 오류 아닌 도구 출력, 부분 일치는 보지 않는다(테스트로 고정).
- 거절이 보이면 result 해석 전에 `SessionError(REFUSAL_MARKER + …)`를 올린다. 메시지에 찾은 흔적과 세션 ID를 적는다
  (`~/.claude/projects/*/<세션>.jsonl`로 찾아갈 수 있게).
- 거절 뒤 이어 간 응답이 영수증을 냈어도 보류한다. 멈춘 내용은 버려졌고 모델은 그것을 다시 쓰지 말라는 안내를 받았으므로,
  그 뒤 결과는 거절된 부분을 조용히 뺐을 수 있다.
- 그다음은 기존 경로: `classify_error` → `model_content_restricted` + `CLAUDE_RESTRICTED_MESSAGE`
  (「Claude가 안전상 이유로 응답을 거절해 보류했습니다. …」), `failure.json`, `content-block.json`(`provider: claude`), `require_unblocked`.
- Codex 실행기·Codex 거절 표식은 그대로. 영수증을 지어내지 않는 규칙도 그대로(이 변경은 영수증을 받지 않는 쪽으로만 움직인다).

## 남은 틈: v3/v4 단계의 거절 표식 (이 PR 밖)
`runner/root_native_json.py` `remember_restriction`은 단계 이름을 `normalize|generate|(source|medical|repair)-[0-3]`로만 받는다.
이번 거절은 `v4-fix-1-1`이라, 분류가 고쳐진 뒤에도 `failure()` 안에서 `Invalid restricted stage`로 멈춘다.
그래서 그 단계의 `failure.json`·`content-block.json`이 남지 않는다. 편 전체 보류 문구(`main`)는 예외 사슬을 따라가
「Claude가 안전상 이유로 응답을 거절해 보류했습니다」로 나온다. v3/v4 단계는 원래 실패하면 관리자 재개 이유 없이 다시 돌지 않는다.
`feat/tree-edge-planner`가 같은 줄(`medical-presuppose` 추가)을 고치고 있어 이 PR에서는 건드리지 않았다(조정 결과).
그 브랜치가 들어간 뒤 `v[34]-…` 단계 이름도 받게 한다. 그러면 Codex의 v4 거절도 이 충돌 대신 정상 거절 표식이 된다.
대시보드 「제안된 아이디어」에 적었다.

## 검사
- `tests/studyez_llm/test_claude.py`: 거절 뒤 이어 간 합성 stream(흔적 셋 전부·각각 하나만), 영수증을 낸 경우, result의 `stop_details`,
  같은 문구가 모델 글·도구 출력·부분 일치로 나오는 경우(거절 아님).
- `tests/runner/test_root_claude_provider.py::test_거절_뒤_이어_간_claude_세션은_실행_실패가_아니라_보류다`: 실제 `claude.run`을
  `NativeJson`으로 돌려 `failure.json` 분류·`content-block.json`(claude)·`require_unblocked`를 본다.
- 새 검사 7개는 고치기 전 코드에서 실패하고 고친 뒤 통과한다.

## 배포·적용
master 병합(자동 배포는 API·웹만) → 러너 `.runtime` 재설치. 이미 끝난 261109_02 보류 기록은 그대로 둔다(제외 문항으로 마쳤다).
