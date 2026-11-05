# 실제 시범 후속 확인

사용자의 “돌아가긴 했는데 잘된 거야?” 확인에서 generation `f0a8f3b68e3642598f85bbf462e1dc55` / job `524`의 웹 응답은 수신됐지만, 현재 블럭 밖의 약리학이라 held된 것을 발견했다. 게시된 뿌리 콘텐츠는 없었다.

- API 후보 `7f4d40dfc9d948f5245a7d9ca063ad80cb4869a562a807fdf181cff9bacdf1c4` → revision `studyez-api-release-1793707198430414200`, 트래픽 100%, health/smoke 통과.
- 계약 72, 러너 전체 492, 관련 격리 서버 검사 통과. 기존 로컬 데스크톱·중지 설정과의 추가 통합 43개 통과.
- 운영 실행 작업이 없음을 확인한 뒤 기존 agent `41304`를 같은 실행 인수로 `13004`에 갱신했다. 남아 있던 자식은 console host뿐이었고 모델/작업 자식은 없었다. 별개 작업과 데스크톱 설정은 변경하지 않았다.
- 동일한 packet과 웹 응답 지문을 확인하고 기존 `resume_job` 서비스로 job `524`만 재개했다. 직접 ChatGPT 접속·웹 재전송·은행 교체는 없었다.

실제 다음 단계에서는 Codex가 `uniqueItems` strict 출력 형식을 HTTP400 `invalid_json_schema`로 거절했다. normalize 실패 ledger와 로그를 보존했다. 해당 후속 수정·제한 복구는 `../2026-11-03-root-schema-compat/`에 기록한다. 이 범위 수정 배포만으로 의학 검수나 콘텐츠 게시가 완료됐다고 간주하지 않는다.

정본 검사/고정 후보/배포 영수증: `tmp/root-web/docs/changes/2026-11-03-root-explicit-job-scope/state.json`.
