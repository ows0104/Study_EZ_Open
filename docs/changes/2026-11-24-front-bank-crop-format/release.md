# 앞 단계 은행 crop 형식 — 배포 준비

## 코드 리뷰·검증 결과
- 변경: 과제문 두 파일에 한 문장, `runner/root_front.py` 검사 7줄, 검사 하나.
- 새 검사는 고침 없는 코드에서 실패하고 고친 코드에서 통과한다.
- `python -m pytest tests/runner -q`: 900 통과·1 건너뜀·1 실패. 실패한 하나(`test_shortcut_installer_supports_korean_filename_in_windows_powershell`)는 worktree에 `.venv`가 없어서다(gpt-6.2 변경 기록과 같다).

## 배포 대상 버전·순서·데이터 변경
- 러너 PC 코드와 지시문만 바뀐다. 서버·웹·DB·계약 변경 없음. master 병합이 API·웹을 다시 배포하지만 내용은 같다.
- 병합 뒤 러너 `.runtime` 재설치 → 261124_01·_03 일감을 queued로 되돌린다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 두 편의 앞 단계 `bank/bank.json` crop이 전부 left<right·top<bottom이고, 렌더를 지나 공개까지 간다.
- 롤백: 이 PR revert 후 재설치.
- 사람 승인: 사용자 「고치고 두 편 재개」(2026-11-24).
