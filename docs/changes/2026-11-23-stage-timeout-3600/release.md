# /4 Codex 단계 시한 3600초 — 배포 준비

## 코드 리뷰·검증 결과
- `pytest tests/runner tests/quizbank`(2026-11-23, worktree): 2,013 통과 · 1 건너뜀 · 1 실패.
  - 실패 `tests/runner/test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`는 worktree에 `.venv/pyvenv.cfg`가 없어서다. #240(2026-11-23-fix-same-question)에서도 같은 실패를 기록했다. 이 변경과 무관하다.
- 시한 검사 `test_claude_단계만_시한이_길다` 통과.

## 배포 대상 버전·순서·데이터 변경
master 병합(러너 코드라 API·웹 동작은 같다) → 러너 `.runtime` 재설치. DB·프롬프트 변경 없음.

## 배포 후 확인·롤백·필요한 사람 승인
- 새 러너 PYTHONPATH가 새 설치본인지 확인. 다음 /4 단계 실패 메시지가 「3600초 안에 끝나지 않았다」로 바뀌는지로 반영을 본다.
- 롤백: 상수 2400, 러너 재설치.
- 병합·재설치·job 728 재실행은 사용자 승인 뒤.
