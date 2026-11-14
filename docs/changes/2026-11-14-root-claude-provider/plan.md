# Main-Quiz 강의별 Claude 출제 경로 — 구현 계획

## 변경 범위·대상 파일·순서

1. **Claude 실행기** — 새 `studyez_llm/claude.py`
   - 실행 파일 찾기: `STUDYEZ_CLAUDE_BIN` → PATH의 `claude` → `~/.local/bin/claude`.
   - 명령: `claude -p --output-format json --model <m>` + 최소 설정 모드, 빈 MCP 설정(`--strict-mcp-config`),
     도구 목록 제한(blind면 없음), `--json-schema`(schema가 있을 때), 시스템 프롬프트, 이미지가 있으면 stream-json 입력.
     정확한 플래그는 설치된 CLI(2.1.282)의 `--help`로 확인하고, 모델 호출 없는 단위 테스트로 명령 배열을 고정한다.
   - 출력 해석: 결과 JSON → spec 요구사항 2의 반환 형식. 거절·한도·빈 응답 판정.
   - 하위 프로세스는 기존 `run_process`(시간 초과 시 자식 트리 종료, `CREATE_NO_WINDOW`)를 쓴다.
2. **공급자 선택** — 새 `studyez_llm/models.py`(`provider_of`, `model_name`, `run`), `studyez_llm/execution.py`(공급자별 slot).
   `codex.model_name`은 gpt 전용 그대로 둔다(기존 호출부 호환).
3. **생성 경로 연결** — `g.codex.run`/`g.codex.model_name`을 `models.run`/`models.model_name`으로:
   `runner/root_native_json.py`(단계 호출·후속 호출·proof model·`validate_stage`가 단계별 모델로 확인),
   `runner/root_front.py`, `quizbank/connection_generate*.py`(identity·manifest model·재개 행), `quizbank/session.py`,
   `quizbank/root_evidence.py`·`root_choices.py`가 쓰는 호출부.
4. **복구 도구 거절** — spec 요구사항 8의 모듈 시작부에 Claude 모델 거절 한 줄.
5. **강의별 지정** — 새 `runner/model_overrides.py`(읽기·형식 검사), `runner/agent.py`(Main-Quiz 일감 명령에 `--model`·로그 한 줄).
6. **문서** — `runner/CLAUDE.md`·`quizbank/CLAUDE.md`에 지정 방법과 범위, `docs/commands.md`에 지정 파일 예시.
7. **실제 적용(사용자 확인 뒤)**
   1. 러너 `.runtime`을 새 코드로 다시 설치(기존 「러너 새 코드 반영」 절차).
   2. `runs/model-overrides.json`에 261109_02 generation과 사용자가 확인한 모델·발언을 적는다.
   3. 관리자 이어 하기(재개 이유: 「Claude Code CLI로 전환, OpenAI 콘텐츠 제한 3회」)로 작업을 대기열에 되돌린다. 운영 DB 쓰기이므로 이 단계도 확인에 포함한다.
   4. 러너가 normalize부터 Claude로 돌린다. 로그·원장·게시 결과를 확인해 `release.md`에 적는다.

겹침 조정(대시보드): `runner/root_front.py`는 ccr-73ec38c7(앞 단계 제목 보류) 행, `runner/connection_generation.py`는
claude/choices-merge 행과 겹칠 수 있다. 이 계획은 connection_generation.py를 고치지 않는다(이미 `model`을 넘긴다).
root_front.py는 호출부 두 줄만 바꾸며, 구현 시작 전에 그 행의 상태를 다시 확인한다.

## 검사 명령과 성공 조건

- 단위(모델 호출 없음, 새 `tests/llm/test_claude.py`·`tests/runner/test_model_overrides.py`):
  명령 배열(도구 제한·설정 무시·MCP 없음·schema·system·이미지 stream-json), 결과 JSON 해석, 거절 → `ContentRestricted`,
  한도 메시지, 재개 사용량 차감, 지정 파일 없음/있음/형식 오류, agent 명령에 `--model`이 붙는 조건.
- 회귀(`regression`): `python -m pytest tests/contracts tests/quizbank tests/runner tests/llm -q` 전부 통과.
  지정 없는 경로의 Codex 명령 배열·원장 내용이 같음을 기존 테스트로 확인.
- 실제 CLI 연기 검사(강의 자료 없음): 빈 work 폴더에서 Claude로 receipt 스키마 응답 1회 — 플래그·출력 형식·세션 ID·사용량 해석 확인.
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
