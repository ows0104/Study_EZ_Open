# Claude 모델 단계 시한 늘리기

## Intent
사용자 「시한을 늘리자」(2026-11-15). 261109_02(레지오넬라·리스테리아·바실루스) 새 필기 판을
Claude(`claude-opus-5-5`)로 출제하는 중 `v4-add-0`이 2400초 시한을 두 번(02:39, 03:28) 넘겨 보류됐다.
두 번째 세션은 붙은 쪽 70장을 한 장씩 읽고 결과 파일을 쓴 뒤 문항을 고치던 중이었다 — 일이 틀린 게 아니라 느리다.

## Spec
- `runner/root_native_json.py` `NativeJson`: 모델이 `claude-…`이면 단계 시한을 `max(timeout, 7200)`초로. Codex(`gpt-…`)는 2400초 그대로.
  형식 확인 후속 호출도 같은 시한.
- `quizbank/connection_generate_v2.py` 의학 독립 검수(blind 호출): Claude면 3600초, Codex는 900초 그대로.
- 프롬프트·스키마·검수 기준·수정 상한·영수증 증명(proof)은 그대로. 시한은 proof에 들어가지 않아 이미 끝난 단계의 검증이 바뀌지 않는다
  (`validate_stage`는 단계 폴더에 보관된 `adapter.py` 사본의 해시를 본다).

## 검사
- `tests/runner/test_root_claude_provider.py::test_claude_단계만_시한이_길다`
- runner·quizbank 관련 131 통과(로컬).

## 배포·적용
master 병합 → 러너 `.runtime` 재설치 → job 620(generation 2bcdcf1f…)을 같은 requestId로 resume.
기록: `runs/_development/2026-11-15-261109_02-v2-claude/`.
