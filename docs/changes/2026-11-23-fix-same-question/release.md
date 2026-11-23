# Main-Quiz /4 고치기는 같은 물음 안에서만 — 배포 준비

## 코드 리뷰·검증 결과

- 새 검사 `tests/quizbank/test_fix_same_question.py` 5개 통과. master 지시문으로 바꿔 돌리면 5개 모두 실패.
- 전체 회귀(development.py verify regression, 2026-11-23): 3,124 통과 · 5 건너뜀 · 1 실패.
  - 실패 `tests/runner/test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`는 worktree에 `.venv/pyvenv.cfg`가 없어서다(로그: Cannot find path …\.venv\pyvenv.cfg). #238 세션도 같은 실패를 「origin/master에서도 같다」고 기록했다. 실패 원인이 worktree 환경이라 지시문 변경과 무관하다.
- 모델 재생은 하지 않았다. 효과는 새 러너의 첫 /4 강의에서 본다.

## 배포 대상 버전·순서·데이터 변경

- 바뀌는 것: v4 지시문 fix.md·item-review.md(러너가 읽는다). 서버·DB·조립·결과 검증 규칙은 그대로다.
- 데이터 변경 없음. 공개 판·문항 ID·학습 기록을 바꾸지 않는다.
- /4 ledger identity가 바뀐다. 진행 중인 /4 실행은 `--resume <이유>`가 필요하다.
- 순서: master 병합(검사 → Cloud Run → Pages 자동, 이 변경은 서버·웹에 영향 없음) → 러너 `.runtime` 재설치(러너 담당 세션과 맞춤).
  지금 러너는 11-19판(a55484c1)이다. #236도 아직 러너에 없으니 함께 재설치하면 된다.

## 배포 후 확인·롤백·필요한 사람 승인

- 첫 새 /4 강의 뒤: 고친 원래 문항(fixes, 되돌리지 않은 것)의 처음 판과 최종 판을 비교한다.
  - 묻는 대상·범주가 바뀐 문항이 0에 가까운가
  - exam_rationale에 「적용하지 않은 이유」가 남은 문항
  - 검토 note의 「별도 문항: …」 수
  - 셋(정답 교체·목록 채우기·한 층)이 여전히 일어나는가
- 롤백: git revert 후 러너 재설치
- 사람 승인: master 병합, 러너 재설치, 운영 재출제. 셋 다 이 작업에서 하지 않는다.
