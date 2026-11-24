# Main-Quiz 생성 시간 단축 2차(300초 선·단계 나란히) — 배포 준비

## 코드 리뷰·검증 결과
- 변경: `studyez_llm/codex.py`(공급자 `studyez`, 재개 거절 때 내장 공급자로 한 번 다시), `quizbank/connection_generate_v4.py`
  (`ahead()`와 미리 시작 네 곳), `quizbank/connection_batches.py`(동시 수 기본값 8), 검사 일곱 개 추가·한 개 수정.
- 검사: `python -m pytest tests/quizbank tests/runner tests/studyez_llm tests/contracts -q`(development.py verify regression, 결과는 state.json).
  바로가기 설치 검사 하나는 worktree에 `.venv`가 없어 뺐다(1차와 같다).
  - 미리 시작을 쓴 실행과 `start_early`를 막은 실행이 같은 `document`·`brief`, 단계마다 같은 이름·입력 지문·출력 지문
    (존재 목표·역방향 목표·늦은 보충 세 경우. 의학 검토 출력은 `reviewed_at` 때문에 제외).
  - 지도 점검이 범위 판정이 돌아오기 전에 시작한다 / 맥락 판정이 늦은 보충의 첫 호출이 돌아오기 전에 시작한다.
  - `batchMode` 없는 ledger는 아무것도 미리 시작하지 않는다.
  - 공급자 설정이 가림·저작 호출 모두에 들어간다 / 재개가 `modelProviderMismatch`면 내장 공급자로 한 번, 다른 경우는 그대로 실패.
- 실제 호출(2026-11-24, 러너 PC, CLI 0.167.0-alpha.3.2):

  | 확인 | 결과 |
  |---|---|
  | 내장 공급자에 `stream_idle_timeout_ms` 지정 | 거절: 「Built-in providers cannot be overridden」 |
  | 새 공급자, idle 1ms | websocket·SSE 모두 idle timeout으로 실패 → 설정이 먹는다 |
  | 새 공급자, idle 900초, 짧은 호출 | 정상 응답 |
  | 40문항 선지 묶음(게시 때 여섯 번 다시 받아 2,504초) | 348초 조용했다가 한 번에 끝남. 378초, 출력 17,496토큰, 오답 154개 |
  | 내장 공급자로 만든 세션을 새 설정으로 재개 | CLI 거절 → 래퍼가 내장 공급자로 다시 재개해 앞 대화의 낱말을 답함 |
  | 새 공급자로 만든 세션을 새 설정으로 재개 | 정상 |

- 확인하지 못한 것: 실제 강의 한 편의 /4를 새 코드로 돌리지 않았다. 나란히 돌린 단계의 절감(계산상 5~6분)과 normalize·front/bank가
  한 번에 끝나는지는 재설치 뒤 첫 출제의 `generation/*.usage.json`·`ledger.json`의 `earlyCalls`로 본다.

## 배포 대상 버전·순서·데이터 변경
- 러너 PC 코드만 바뀐다. 서버·웹·DB·계약·지시문 변경 없음. master 병합이 API·웹을 다시 배포하지만 내용은 같다.
- 병합 뒤 러너 `.runtime` 재설치. 도는 일감이 없을 때 바꾼다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인(첫 Main-Quiz 출제): `ledger.json`의 `earlyCalls`에 `v4-map-check-presuppose`·`v4-supplement-normalize-discriminate`·
  `v4-map-check-late`·`v4-context-0`가 `used: true`로 있는지, normalize·v4-add·front/bank의 `duration_ms`가 한 번에 끝난 길이인지,
  Codex 세션 기록에 301초 간격의 `token_count`가 없는지.
- 첫 호출이 「config」 오류로 실패하면(CLI가 공급자 칸을 바꾼 경우) 이 PR을 revert하고 러너 재설치.
- 사람 승인: 병합·재설치는 사용자 「2차 적용해」로 진행. 맥락 수선을 뺄지는 설명 뒤 사용자 결정.
