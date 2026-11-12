# Main-Quiz 공개된 판 새로 출제(관리자 명시) — 배포 준비

## 코드 리뷰·검증 결과
- 로컬 `-m tests root_restart root_api root_one_click` 통과. 독립 리뷰 없음.

## 배포 대상 버전·순서·데이터 변경
- 서버만. 병합 = API 배포. DB 변경 없음.

## 배포 후 확인·롤백·필요한 사람 승인
- `/api/health` revision, 261110_03 요청이 queued로 들어가고 게시 뒤 control.revision이 새 판인지.
- 롤백: git revert.
