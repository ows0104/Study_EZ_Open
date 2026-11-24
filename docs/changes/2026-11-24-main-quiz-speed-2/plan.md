# Main-Quiz 생성 시간 단축 2차(300초 선·단계 나란히) — 구현 계획

## 변경 범위·대상 파일·순서
1. `studyez_llm/codex.py`: 공급자 `studyez` 정의(`command`), 재개 거절 때 내장 공급자로 한 번 다시(`_run`).
2. `quizbank/connection_generate_v4.py`: `ahead()`로 전제 지도 점검·역방향 normalize·보충 지도 점검을 미리 시작,
   늦은 보충 앞에서 `v4-context-0`을 미리 시작. 차례·입력을 만드는 코드는 옮기기만 한다.
3. `quizbank/connection_batches.py`: 동시 수 기본값 8.
4. 검사: `tests/studyez_llm/test_codex.py`(공급자 설정·재개 폴백), `tests/quizbank/test_pipeline_overlap.py`(미리 시작한 실행 = 차례로 돈 실행),
   `tests/quizbank/test_pipeline_resilience.py`(기본값).
5. 실제 호출 확인 셋: 긴 응답 한 번, 내장 공급자 세션 재개, 새 공급자 세션 재개.

## 검사 명령과 성공 조건
- `python -m pytest tests/quizbank tests/runner tests/studyez_llm -q` — 새 검사 통과, 회귀 없음.
- 긴 응답: 40문항 선지 묶음(1.7만 토큰)이 다시 받기 없이 끝난다.

## 위험·복원·승인할 범위
- 위험: 모든 Codex 호출의 공급자 설정이 바뀐다(예습·복습 덱 포함). CLI가 판을 올리며 공급자 칸을 바꾸면 호출이 실패할 수 있다 —
  실패는 첫 호출에서 「config」 오류로 바로 드러난다.
- 위험: 쓰이지 않은 `v4-context-0` 미리 시작은 호출 하나의 토큰을 버린다(늦은 보충이 문항을 뺄 때만).
- 복원: 이 PR을 revert하고 러너 재설치. 새 공급자로 만든 세션은 옛 코드로 재개되지 않는다(그 실행은 `--resume`으로 새 세션).
- 승인 범위: 위 파일과 이 폴더, 로컬 검사·실제 호출 확인·PR·병합·러너 재설치(사용자 「2차 적용해」). 단계 삭제는 따로.
