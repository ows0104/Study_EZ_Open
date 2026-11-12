# Main-Quiz 접수: 문항 오류 판별을 문제은행의 실제 문항 번호로 — 배포 준비

## 코드 리뷰·검증 결과
- `pytest tests/quizbank tests/runner/test_root_front.py tests/runner/test_front_overlap.py`: 1022 통과, 1 건너뜀. 보류된 실제 문제은행 대조 통과. 독립 리뷰 없음.

## 배포 대상 버전·순서·데이터 변경
- 러너·생성기만. 병합 뒤 러너 재설치 → 261110_03 이어 하기.

## 배포 후 확인·롤백·필요한 사람 승인
- 261110_03 게시와 control.revision 교체. 롤백: git revert, 러너 `.runtime/main-quiz-c401f8626b08`.
