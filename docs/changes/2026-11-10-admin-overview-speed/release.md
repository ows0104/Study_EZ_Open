# 관리 탭 로딩 지연 제거 — 배포 준비

## 코드 리뷰·검증 결과
- 서버 `python -m tests` 130/132 통과(격리 SQLite, `PYTHONPATH`=이 worktree). 실패 2개
  `test_root_map_tree`·`test_root_map_tree_v3`는 빌려 쓴 venv에 `pymupdf`가 없어 import에서 멈춘 환경 문제다.
  이번 변경 파일과 무관하다. CI가 다시 판정한다.
- `test_admin_egress`: 요약 일치(`revision` 제외), 한 번 훑기(`json_each` 1회, `->` 없음), JSON null 행, 캐시 무효화 통과.
- 운영 DB 읽기 전용 대조: 새 쿼리로 만든 요약이 전체 행으로 만든 `summary()`와 같다(작은 은행 5편, 그때는 `revision` 포함).
- 운영 데이터로 만든 overview 응답: 20.0MB(gzip 4.35MB) → `revision`을 빼면 0.89MB(gzip 0.135MB).

## 배포 대상 버전·순서·데이터 변경
- master 병합 → GitHub 검사 → API 자동 배포. 웹 변경 없음.
- DB 스키마·데이터 변경 없음.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: Cloud Run 로그에서 `GET /api/admin/overview`의 `responseSize`가 1MB 안쪽, 지연이 10초대에서 내려왔는지.
  `GET /api/admin/bank-feedback` 지연이 3초대에서 내려왔는지. 관리 화면 퀴즈 탭의 Quiz Bank 줄(문항 수·검토 표시)이 그대로인지.
- 롤백: git revert 후 master, 또는 이전 Cloud Run revision.
- 사람 승인: 「사람에게 묻는 것」에 닿지 않는다(코드만, 되돌릴 수 있음). 근거는 intent.md의 사용자 요청 원문.
