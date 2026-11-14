# Main-Quiz 강의별 Claude 출제 경로 — 배포 준비

## 코드 리뷰·검증 결과
- 회귀 `pytest tests/contracts tests/quizbank tests/runner tests/studyez_llm`: 2329 통과·1 건너뜀(실패 0).
  기록 `runs/_development/2026-11-14-root-claude-provider/1794641684093275200-regression.log`.
  첫 실행(…1794638094162300900)은 바로가기 설치기 검사 1개가 새 worktree에 `.venv/pyvenv.cfg`가 없어 실패했다
  (2026-11-12 dedupe-published에도 기록된 환경 문제). worktree에 운영 `.venv` junction을 두고 다시 돌려 통과했다.
- 새 검사 21개(모델 호출 없음): `tests/studyez_llm/test_claude.py` 10, `tests/runner/test_root_claude_provider.py` 11
  (명령 배열·설정 무시·도구 제한·긴 인자·이미지·거절·오류·재개 사용량·자리·지정 파일·러너 명령·공급자별 거절 표식).
- 실제 CLI 연기 검사(2026-11-14, Claude Code 2.1.282, 사용자 로그인 뒤, 강의 자료 없음, `claude-opus-5-5`):
  - 작업 실행: 빈 work 폴더에서 Python으로 result.json 작성·check_result.py 실행·영수증 반환 → 파일 SHA 일치, 5턴,
    사용량·모델 기록 정상. `--safe-mode`·`--setting-sources ""`·`bypassPermissions`·`--json-schema`·`--system-prompt` 수용.
  - 같은 세션 이어 하기(`--resume`): 같은 세션 ID·같은 영수증, 호출분 사용량.
  - 가림 실행(도구 없음): 구조화 출력 정상.
  - 이미지: 메시지에 붙인 PNG와 경로로만 알린 PNG(Read 도구) 모두 그림 속 숫자를 읽음.
- 자체 리뷰: 지정 없는 Codex 경로는 `codex.run`에서 분기 전과 같은 인자로 `_run`을 부른다(자리 한도 값도 같음).
  Codex 거절 표식 proof 모양은 그대로이며(검사로 확인), 모델을 모르는 호출은 지금처럼 모든 표식에 막힌다.
  남은 위험: Claude의 Bash는 Codex처럼 OS 샌드박스에 갇히지 않는다(도구·cwd 제한, 설정·MCP 없음으로 줄임).
  Anthropic 쪽 안전 기준에 걸리면 보류로 멈춘다.

## 배포 대상 버전·순서·데이터 변경
- 출제 쪽(러너 `.runtime` 설치본)만 영향. 서버·웹·DB·프롬프트 변경 없음. master 자동 배포(API·Pages)는 코드 차이 없이 돈다.
- 순서: PR 병합 → 병합 커밋으로 `.runtime/main-quiz-<sha12>` 설치(바탕화면 바로가기 교체) → 도는 Main-Quiz 작업이 없을 때 에이전트 교체.
- 데이터 변경 없음. `runs/model-overrides.json`은 만들지 않는다(실제 적용은 별도 확인).

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 에이전트 pid의 PYTHONPATH가 새 설치본, `runs/agent.log`에 러너 시작 줄. 지정 파일이 없으므로 모든 작업이 지금처럼 Codex.
- 롤백: PR revert 또는 바로가기를 이전 설치본(`shortcut-before.lnk`)으로 되돌리고 에이전트 재시작.
- 별도 확인(이 배포에 포함하지 않음): 261109_02에 Claude 지정·관리자 재개(Anthropic 전송·운영 DB 쓰기).
