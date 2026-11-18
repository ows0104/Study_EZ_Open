# Main-Quiz 복습 간격 2차 — 배포 준비

## 코드 리뷰·검증 결과

- `server/tests/test_root_review_curve.py`: spec 표(네 평가 × 네 등급), 난이도(Again·Hard 뒤 Good), 늦게 맞힌 보너스,
  같은 학습일 반복, 시험 압축 등급, 1차 규칙(/3 숙련도·도움 뒤 고른 평가)을 확인.
- 서버 전체 검사(server/에서 메인 체크아웃 venv, PYTHONPATH=.., 각 검사의 격리 sqlite): 159/161. 실패 2개(test_root_map_tree, _v3)는 venv에 PyMuPDF가 없는 환경 문제.
- 기존 검사: test_main_quiz_four_ratings·test_root_tier는 /4·curveParameters 저장, test_root_tier는 Good 3번(8번이면 모든 등급이 30일 상한)과 「중요도는 M을 안 바꾼다」로.
- 미확인: 운영 기록으로 재생한 실제 강의의 오늘 복습 수.

## 배포 대상 버전·순서·데이터 변경

- 서버만. DB·API 형식 변경 없음. 새 평가 사건 payload에 `ratingPolicy` /4, `curveParameters` 추가.

## 배포 후 확인·롤백·필요한 사람 승인

- 사용자 「검사 끝나면 바로 병합해서 배포해줘」(2026-11-18).
- 확인: 배포 워크플로의 API 배포 성공.
- 롤백: `git revert`(plan.md).
