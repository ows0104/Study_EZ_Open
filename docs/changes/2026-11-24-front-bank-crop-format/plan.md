# 앞 단계 은행 crop 형식 — 구현 계획

## 변경 범위·대상 파일·순서
1. `content/prompts/learning-links/map-tree/bank-task.md`·`bank-task-v4.md` 둘째 줄 뒤에 형식 한 문장.
2. `runner/root_front.py` `Front.bank` 검사에 crop 순서 확인(오류 문구에 문항 ID·값·형식).
3. `tests/runner/test_root_front_v3.py`: 폭·높이 crop이 한 번 되돌아가 고쳐진 값으로 끝나는 검사(고침 없이 실패 확인).

## 검사 명령과 성공 조건
- `python -m pytest tests/runner -q` — 회귀 없음.

## 위험·복원·승인할 범위
- 위험: 앞 단계 은행이 crop 때문에 후속 한 번을 더 쓸 수 있다. 두 번 틀리면 지금처럼 그 단계가 실패로 남는다(앞 단계 안에서 멈춘다).
- 복원: 이 PR revert 후 러너 재설치.
- 승인 범위: 위 파일과 이 폴더, PR·병합·러너 재설치, 261124_01·_03 다시 돌리기(사용자 「고치고 두 편 재개」).
