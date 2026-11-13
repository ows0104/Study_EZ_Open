# Main-Quiz 보충 포인트 ID 충돌 수정 — 배포 준비

## 코드 리뷰·검증 결과
- `attach_points`에 `reserved`(brief 포인트 ID)를 더해 새 번호가 brief 전용 포인트를 비켜 간다. 기본값이면 번호는 전과 같다.
  `duplicate_of`는 여전히 포인트 문서의 포인트만 가리킬 수 있다.
- 새 테스트: v3 `test_supplement_point_ids_skip_brief_only_points`, v4 `test_supplement_points_have_no_basis`에 한 줄.
- `pytest tests/contracts tests/quizbank` 1401 통과(verify 기록), `tests/runner/test_root_native_v3.py`·`test_front_overlap.py` 26 통과.
- 실제 재현(261113_02 산출물: 포인트 87, brief-fix 뒤 brief 93, Q092 보충): 옛 코드 P088, 새 코드 P094.
  supplement-normalize 출력의 P088을 P094로 바꿔 넣으면 `check_supplement_normalize`·`extend_brief` 통과(포인트 94, 새 목표 TQ001).

## 배포 대상 버전·순서·데이터 변경
- 출제 쪽(러너 `.runtime` 설치본)만 영향. 서버·웹·DB·프롬프트 변경 없음.
- master 병합 뒤 러너 새 코드 반영 절차로 `.runtime`을 새로 깐다.

## 배포 후 확인·롤백·필요한 사람 승인
- 261113_02 재실행: 완료 단계는 ledger에서 재사용되고 `v4-supplement-normalize`만 P094 입력으로 다시 호출되는지 로그로 확인.
- 롤백: PR revert.
- 사람 승인: master 병합(자동 배포), 러너 재설치·261113_02 재실행.
