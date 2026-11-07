# Release

대상: `codex/review-prompt-simple`, 최신 origin/master 2489e52e에서 분리한 복습 문구 수정. 최종 revision과 검사·리뷰·배포 결과는 완료 후 기록한다.

복습 기본 문구를 사용자 지정 한 문장으로 교체하고 교수 정보만 한 줄로 덧붙인다. DB/schema/API/첨부/은행/학습 기록 변경은 없다. 기존 개인 문구는 보존하며 기본값을 쓰거나 기본값으로 되돌린 경우 새 문구를 사용한다.

검사: review-prompt, web. 직접 diff 리뷰 후 development.py의 revision-bound release gate를 확인한다. 일반 코드의 PR 검사 → master 병합 → 같은 SHA의 API/Pages 자동 배포를 확인한다. 복원은 변경 커밋의 revert PR이며 데이터 복원은 필요하지 않다.

2026-11-07 검증 완료: review-prompt 5/5 통과, 웹 typecheck와 정식 build 통과. 사용자 예시의 완전 일치 출력, 시간표와 실제 필기 교수가 다른 경우, 미상·공동 교수, 기존 개인 문구, 예습 분리를 확인했다. 코드 리뷰: 파싱·첨부·저장 API를 바꾸지 않고 출력 두 곳만 수정했다. 은행 프롬프트의 오래된 버전 고정 검사는 현재 전달 계약 검사로 갱신했다. 미해결 문제 없음. 배포 성공은 실제 원격 검사/게시 확인 전까지 주장하지 않는다.

최종 결과: PR #15를 `2d85e7936651ff6c3b7c83c2dda7c13ed9143215`로 병합했다. 일반 코드 자동 배포 승인에 따라 PR/master 전체 검사와 API/Pages 배포가 모두 성공했다. 실제 공개 자산의 새 기본 문구·교수 한 줄·이전 안내 제거, API 동일 revision/401을 확인했다. 상세 근거와 Maintain 확인은 [deployment.md](deployment.md)에 남겼다.
