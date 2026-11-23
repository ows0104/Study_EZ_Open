# Main-Quiz /4 중요도 근거가 답 전체를 덮게 — 배포 준비

## 코드 리뷰·검증 결과

- 새 검사 `tests/quizbank/test_basis_covers_answer.py` 16개.
  - 지시문 R1~R4 문장(근거는 답 전체 — 처음 문제은행·add·fix, 강조된 원소는 따로 묻는 문항으로 살림·목록 문항은 사례마다 판단·「나머지 …」 금지, fix의 같은 물음·예외 셋, 검토의 「별도 문항: …」)
  - 중복 방지: 고치기 입력 `asked`, 새 문항의 재확인이 목표의 다른 근거 문항도 읽고 그 근거는 처음 것을 둠, 겹치면 중복으로 합쳐짐
  - fix-splits/1: 스키마 선택(러너 포함), 새 문항 계약(범위·split_from·concept·point_ids·근거 누락), 실행 안 동작
    (자기 근거·다시 검토·커버 재확인·과제, 원래 문항이 되돌려지면 함께 버림, 옛 ledger는 새 ID 없음),
    동시 묶음의 ID 범위와 순차 실행과 같은 결과(동시 실행만 `v4-coverage-merge-0` 한 번 더)
  - 첫 12개는 이 변경 전 코드(f5bda467)에서 11개가 실패했다. 통과하는 하나는 「옛 ledger는 이전 그대로」다.
- 전체 `pytest tests studyez_contracts`(development.py verify regression, 2026-11-23): 3,134 통과 · 4 건너뜀 · 1 실패(추가 결정 반영 뒤 다시 돌림).
  - 실패 `tests/runner/test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`는
    이 worktree에 `.venv/pyvenv.cfg`가 없어서다. origin/master 체크아웃에서도 같은 오류로 실패한다(이 변경과 무관).
- `measure.py`를 운영 runs 96개에 다시 돌려 의도 문서의 수치(A 60/1,071, B 93/613)가 그대로임을 확인했다. 새 `split_questions` 수는 기존 실행에서 0이다.
- 모델 실행(재생)은 하지 않았다. 지시문의 효과는 새 러너의 첫 강의에서 본다(아래).

## 배포 대상 버전·순서·데이터 변경

- 바뀌는 것: v4 지시문(add·fix·item-review), 러너 앞 단계의 처음 문제은행 지시문(`map-tree/bank-task-v4.md`), v4 고치기 계약(`studyez_contracts.roots.generation_v4`), 러너의 v4 고치기 스키마 선택,
  /4 생성기와 묶음 합치기. 서버 코드·DB·조립·결과 검증 규칙은 그대로다.
- 데이터 변경 없음. 공개 판·문항 ID·학습 기록·검수 이력을 바꾸지 않는다. 운영 재출제를 하지 않는다.
- 지시문이 바뀌어 /4 ledger identity가 바뀐다. 진행 중인 /4 실행은 `--resume <이유>` 없이는 이어지지 않는다(#236과 같은 영향).
  `fixSplits` 표시는 새 ledger에만 붙고, 이어 가는 옛 ledger는 새 ID 없이 이전처럼 고친다.
  앞 단계는 이미 끝난 문제은행 단계를 그 폴더의 옛 지시문 그대로 재사용한다. 새 앞 단계부터 새 처음 문제은행 지시문을 쓴다.
- 순서: master 병합(검사 → Cloud Run → Pages 자동) → 러너 설치본 갱신. 병합과 러너 재설치는 #236과 시점을 맞추고,
  러너 담당 세션과 사용자 승인 뒤에 한다. 이 PR은 Draft까지다.
- 호환: 옛 서버는 새 결과를 받는다(새 문항은 접수 문항이 아니고 `fixes` 행의 덧붙은 칸은 읽지 않는다). 옛 러너는 새 서버에 이전 결과를 낸다.

## 배포 후 확인·롤백·필요한 사람 승인

- 첫 새 /4 강의 뒤 `python docs/changes/2026-11-23-basis-covers-answer/measure.py --runs <runs>`로 본다.
  - B(근거가 답 일부만 덮음) 비율이 줄었는가, A(고치기 확장 2단위+) 비율이 줄었는가
  - `split_questions kept/dropped` 수와 그 문항이 과제가 되었는가(목표 없음으로 남은 수는 readiness의 unplaced)
  - 강조된 원소 문항이 생겼는가, 목록 문항을 버린 경우가 존재 문항·목표가 요구한 목록이 아니었는가, 문항 수 증가
  - tier 분포가 크게 내려가지 않았는가(근거를 지나치게 빼는 위험)
- 롤백: git revert 후 러너 재설치. 데이터 변경이 없어 되돌릴 기록이 없다.
- 사람 승인이 필요한 것: master 병합(자동 배포), 러너 재설치, 운영 강의 재출제. 셋 다 이 작업에서 하지 않았다.
