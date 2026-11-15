# 공개판 재사용 경로(중복만·못 붙은 문항만)가 공개 판의 작업을 이전 판으로 — 구현 계획

## 변경 범위·대상 파일·순서
1. `server/app/routes/root_generation.py`: `restart_target`에 `from_published`(R1), `request`에서 duplicatesOnly·unplacedOnly일 때 넘김, restart 요청의
   같은 입력 재사용에서 끝난 작업 제외(R2).
2. `server/tests/test_root_restart.py`: 수용 기준.

## 검사 명령과 성공 조건
`cd server && PYTHONPATH="..;." .venv/Scripts/python -m tests root` — 알려진 실패(pymupdf 없는 map_tree 2개) 외 통과. PR CI 통과.

## 위험·복원·승인할 범위
- 위험: 공개 판이 다른 경로(수동 등)로 올라온 강의는 재사용 경로가 409 — 그 경우 재사용할 단계도 없으니 맞는 거절.
- 복원: 병합 되돌리기(API 자동 배포).
- 승인: 사용자 「고쳐서 재요청」 — 수정·병합·261106_06 재요청까지.
