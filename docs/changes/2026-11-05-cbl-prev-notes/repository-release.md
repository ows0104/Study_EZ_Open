# 저장소 통합·자동 배포 승인

실제 배포 완료: [고정 버전·검사·배포·사후 확인 기록](repository-deployment.md). 운영 Git SHA는 `5c56d462078527470221b2722ba81e15db512a7c`다.

2026-11-05 사용자가 ‘일단 여기까지 커밋, 푸시하고 배포하자.’라고 요청했다. 기존 교수별 예습 기능 운영 기록과 CBL 3개 _pairs/원본 대조·적용 기록을 codex/cbl-prev-notes 브랜치에 모아 master 대상 PR로 검토·검사하고, 성공 후 병합 및 같은 Git SHA의 API·웹 자동 배포를 완료하는 승인이다. 앞서 적용한 세 PDF/선택 메타데이터는 다시 변경하지 않는다.

배포 전 운영 코드 Git SHA는 c86e15fbfd7404255c66bbb30e4ccf74fe2f952b다. 이번 PR의 기능 런타임 소스는 이 버전과 동일하며, 세 _pairs 키와 작업/운영 검증 기록이 추가된다. 원본 PDF·비공개 스냅샷·학습 내용·인증정보는 커밋하지 않는다. 별개 feedback-schema-compat 작업 폴더는 포함하지 않는다.

검사 경로는 docs/development/collaboration.md의 SHA별 자동 배포다. 기존 source-review/selection/preservation 로컬 검사와 실제 운영 적용 영수증을 보존하고, PR 및 병합된 SHA의 Tests and build를 모두 통과한 뒤 API → 동일 SHA 확인 후 Pages 순서로 진행한다. Actions 배포 영수증, 운영 health SHA/보호 경로 401, Pages production success 및 실제 CBL 표시를 사후 확인한다. 수동 후보 명령을 실행한 것처럼 기록하지 않는다.

롤백은 배포 직전 실제 API 트래픽/Pages 성공 버전을 확인해 보존하고 필요시 해당 버전으로 복원한다. 기존 자료 연결과 학습 기록을 되돌리지 않는다. 코드 병합/배포 확인이 끝나면 대시보드 진행 행을 완료 기록으로 옮긴다.
