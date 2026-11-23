# /4 Codex 단계 시한 3600초 — 설계

## 요구사항과 수용 기준
- `runner/root_native_json.py`: `CODEX_TIMEOUT=3600`, `NativeJson(timeout=CODEX_TIMEOUT)` 기본값.
  `timeout_for`는 그대로 — Claude면 `max(timeout, 7200)`, 아니면 `timeout`.
- 검사 `tests/runner/test_root_claude_provider.py::test_claude_단계만_시한이_길다`가 Codex 3600·Claude 7200을 고정한다.

## 책임·입출력 계약·오류 상태
시한만 바뀐다. 프롬프트·스키마·검수 기준·영수증 proof·실패 분류(`[MODEL_TIMEOUT]`, 자동 재시도 없음)는 그대로.

## 호환성과 데이터 보존
시한은 proof에 들어가지 않는다. 끝난 단계는 단계 폴더에 보관된 `adapter.py` 사본으로 검증되므로 다시 돌지 않는다
(2026-11-15-claude-stage-timeout과 같다). 기존 문항·ID·기록 변경 없음. DB 변경 없음.
