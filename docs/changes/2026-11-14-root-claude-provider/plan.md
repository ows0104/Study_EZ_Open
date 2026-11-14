# Main-Quiz 강의별 Claude 출제 경로 — 구현 계획

## 변경 범위·대상 파일·순서

1. **Claude 실행기** — 새 `studyez_llm/claude.py`
   - 실행 파일: `STUDYEZ_CLAUDE_BIN` → PATH의 `claude` → `~/.local/bin/claude(.exe)`.
   - 명령: `claude -p --model <m> --input-format stream-json --output-format stream-json --verbose --safe-mode
     --setting-sources "" --strict-mcp-config --disable-slash-commands --tools <작업 도구|"">`, 작업 실행은
     `--permission-mode bypassPermissions`, 가림 실행은 `--no-session-persistence`. `--system-prompt`·`--json-schema`·`--resume`.
   - 출력 해석: 마지막 `result` 이벤트 → spec 요구사항 2의 반환 형식. 거절·오류·빈 응답 판정.
   - 하위 프로세스는 기존 `run_process`(시간 초과 시 자식 트리 종료, `CREATE_NO_WINDOW`).
2. **공급자 선택** — `studyez_llm/codex.py`: `model_name`이 `claude-…`도 받고 `provider()` 추가, `run()`이 Claude 모델이면
   같은 `exclusive`·`slot`(Claude 자리)·사용량 기록 안에서 `claude.run`을 부른다. `execution.slot(pool=)`, `claude_slot_limit()`.
3. **생성 경로** — `runner/root_native_json.py`: Claude 거절 판정·메시지, 거절 표식의 공급자 기록과 공급자별 차단
   (`require_unblocked(out, model)`), Claude 단계의 check_result.py Python은 호스트 인터프리터. 다른 호출부는 그대로다.
4. **복구 도구** — 코드 변경 없음(spec 요구사항 8). 문서에 전역 모델을 Claude로 두지 말라고 적는다.
5. **강의별 지정** — 새 `runner/model_overrides.py`(읽기·형식 검사), `runner/agent.py`(Main-Quiz 일감 명령에 `--model`,
   형식 오류 보류, 로그 한 줄).
6. **문서** — `runner/CLAUDE.md`에 지정 방법과 범위, `docs/commands.md`에 지정 파일 예시.
7. **실제 적용(사용자 확인 뒤)**
   1. 러너 `.runtime`을 새 코드로 다시 설치(기존 「러너 새 코드 반영」 절차).
   2. `runs/model-overrides.json`에 261109_02 generation과 사용자가 확인한 모델·발언을 적는다.
   3. 관리자 이어 하기(재개 이유: 「Claude Code CLI로 전환, OpenAI 콘텐츠 제한 3회」)로 작업을 대기열에 되돌린다. 운영 DB 쓰기이므로 이 단계도 확인에 포함한다.
   4. 러너가 normalize부터 Claude로 돌린다. 로그·원장·게시 결과를 확인해 `release.md`에 적는다.

겹침 조정(대시보드): 구현은 `runner/root_front.py`·`runner/connection_generation.py`를 고치지 않는다(앞 단계 제목 보류
ccr-73ec38c7은 master 병합 확인, choices-merge 행과 겹치는 파일 없음).

## 검사 명령과 성공 조건

- 단위(모델 호출 없음, 새 `tests/studyez_llm/test_claude.py`·`tests/runner/test_root_claude_provider.py`):
  명령 배열(도구 제한·설정 무시·MCP 없음·schema·system·긴 인자·이미지 stream-json/경로 안내), 결과 JSON 해석,
  거절 → `model_content_restricted`(Claude 메시지), 오류·중단·시간 초과, 재개 사용량, Claude 자리,
  지정 파일 없음/있음/형식 오류, agent 명령에 `--model`이 붙는 조건, 공급자별 거절 표식(Codex 표식은 Claude를 막지 않음·
  Claude 표식은 Claude만 막음·Codex 표식 모양 불변).
- 회귀(`regression`): `python -m pytest tests/contracts tests/quizbank tests/runner tests/studyez_llm -q` 전부 통과.
  지정 없는 경로의 Codex 명령 배열·원장 내용이 같음을 기존 테스트로 확인.
- 실제 CLI 연기 검사(강의 자료 없음): 빈 work 폴더에서 Claude로 receipt 스키마 응답 1회 — 플래그·출력 형식·세션 ID·사용량 해석 확인.
  2026-11-14 이 PC의 Claude Code 로그인이 만료(`claude auth status`: loggedIn false)되어 있어, 사용자가 로그인한 뒤 실행한다.
- 실제 적용 성공 조건: 261109_02가 게시되고(서버 `status: ready`), 원장 단계의 proof model이 Claude, 거절·보류 없이 끝남.
  거절되면 그 증거를 보존하고 보고한다(성공으로 세지 않는다).

## 위험·복원·승인할 범위

위험
- Anthropic 쪽 생물학 안전 기준에도 걸릴 수 있다 → 보류로 멈추고 보고. 자동 재시도·우회 없음.
- Claude Code CLI의 Windows 동작: OS 샌드박스가 Codex만큼 강하지 않다. 도구 제한·cwd 고정·설정 무시로 범위를 줄이지만,
  Bash 허용은 남는다(모델이 로컬 코드로 result.json을 쓰고 check_result.py를 돌려야 한다).
- CLI 플래그·출력 형식이 버전마다 바뀔 수 있다 → 실행기 시작 시 버전을 기록하고, 해석 실패는 단계 실패로 처리.
- 구독 사용량 한도 → 기존 사용량 한도 처리(재개 시각 기록·대기).

복원
- 코드: PR revert. 지정 파일에서 항목을 지우면 그 강의는 다시 Codex로 돈다(재개 이유가 필요).
- 데이터: 261109_02의 Claude 산출물은 같은 generation 폴더에 남고, 다시 돌릴 때는 기존 `.resume-<k>/` 보관 규칙을 따른다.

승인할 범위
- 구현·검사·PR·병합·러너 배포(되돌릴 수 있는 코드 배포): 이 계획에 대한 사용자 승인으로 진행.
- **따로 확인받을 것:** 변경 범위 7의 실제 적용(261109_02 자료를 Anthropic 모델로 보내는 것, 모델 선택, 운영 DB 재개 쓰기).
