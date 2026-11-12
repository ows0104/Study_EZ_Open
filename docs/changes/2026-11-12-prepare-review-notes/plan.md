# Main-Quiz 미리 받기: 검수 메모를 판마다 한 번 — 구현 계획

## 변경 범위·대상 파일·순서
1. `server/app/root_learning/review_notes.py`(새). 2. `server/app/routes/root_learning.py`의 `active_generation`·`revealed_answer`만
   (「시험일 미정」·「개념 지도 분리」 세션과 같은 파일 다른 함수 — 사용자 결정으로 병행). 3. `server/tests/test_root_generation.py`.

## 검사 명령과 성공 조건
- `server/.venv/Scripts/python.exe -m tests` 전체(알려진 환경 실패 `root_map_tree*`만 허용).
- `test_root_generation`: 미리 받기 3번·답 보기 3번에 result 읽기 1번(캐시를 끄면 실패하는 것 확인), 모든 문항의 메모가 예전 식과 같음.
- 메모를 다루는 시험 `root_quiz_curation`·`root_replacement_import`·`root_reviewed_import`·`bank_publication` 통과.
- 운영 읽기 전용: 3,578문항 불일치 0.

## 위험·복원·승인할 범위
- 위험: 인스턴스 메모리에 메모 묶음(작다)만 더해진다. 복원: git revert. 승인: 사용자 요청 범위의 서버 코드, 병합(자동 배포).
