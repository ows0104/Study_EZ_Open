# 개인 수정한 Main-Quiz 문항의 선지 유지 — 배포 준비

## 코드 리뷰·검증 결과
`-m tests root main_quiz route_contract`: 44개 중 43개 통과. `test_root_map_tree_v3`는 빌린 venv에 pytest가 없어 import 단계에서 멈춤(수정 전 master 코드에서도 같음, CI에서 확인).
새 절은 수정 전 코드에서 실패(KeyError: mcq_choices), 수정 후 통과.

## 배포 대상 버전·순서·데이터 변경
서버만. DB·asset·문항·학습 기록 변경 없음. master 병합 시 API 자동 배포.

## 배포 후 확인·롤백·필요한 사람 승인
배포 후 객관식 모드에서 발문만 고친 문항의 선지가 유지되는지 확인. 롤백은 커밋 revert. master 병합(=배포)은 사람 승인.
