# 한 번 누르는 뿌리 학습 — 운영 확인

사용자의 원클릭 실행 요청 및 기존 운영 배포·실제 자료 1건 실행 승인을 적용했다. 기본 버튼에서 별도 지도·포인트 파일 없이 등록된 원본을 자동전송한다. 기존 지도·포인트 사용은 접힌 설정에 보존한다.

- 웹 최종 수정: Pages `56553b7c-ddef-492f-af4d-5cdf4c6ab524`, health 및 읽기 전용 smoke 통과.
- 웹 고정 후보: `9a37910cb3e6b636ca13e4ffecd1df2a035646c944f007312202b95662d6075c`.
- API 최종 수정: `studyez-api-release-1793703305072532800`, 트래픽 100%, health 및 읽기 전용 smoke 통과.
- API 고정 후보: `481fde795349d840f8910a8f1557c6e4b90b3600d6a71041978e429fa8fbcfb2`.
- 현재 소스: `6e1dc7a1c212c5dbaa45b18c9abf419c189655cf68fa14ca540f3e26f1275836`. 7개 필수 검사 통과. 정본 검증·배포 영수증은 `tmp/root-web/docs/changes/2026-11-03-root-one-click/state.json`에 보존한다.
- DB 마이그레이션·공개 범위 확대 없음. 다른 작업의 변경은 배포 사본에 섞지 않았다.

첫 운영 클릭은 개발용 사본 저장 함수 때문에 모델 호출 전 HTTP 500으로 끝났다. 운영 기록에서 생성 작업과 전송이 없음을 확인한 뒤 `upload_fileobj`로 고쳤다. 실제 클라우드 어댑터 분기를 통한 bytes/MIME 보존과 실패 시 503·작업 미등록 검사를 추가했다. 이후 API를 다시 고정·검증·배포했다. 실패한 자료나 검수 기록을 지우거나 횟수를 초기화하지 않았다.

추가 점검에서 전용 RootLearningPage의 응답 수신 연결이 빠지고 브라우저 fixture가 이를 대신 추가한 것을 발견했다. 실제 페이지에 기존 수신 hook을 붙이고 fixture 보충을 제거했다. 실제 페이지의 회수→러너→게시 검사를 다시 통과한 후 웹만 고정·배포했다. 20:04 KST에 같은 Study EZ 탭을 새 웹으로 새로고침했다. 확장은 미저장 응답을 주기적으로 재전달하므로 이미 보낸 요청은 유지하며 재전송하지 않았다.

## 실제 시범 1건

2026-11-03 19:57 KST경 Study EZ 콜린성 약리학(1) 화면의 **뿌리 학습 자동전송** 버튼을 한 번 눌렀다. ChatGPT 탭에는 직접 들어가지 않았다.

- Generation: `f0a8f3b68e3642598f85bbf462e1dc55`, job `524`.
- 입력: 등록된 올해 PDF와 족보. `inputMode=source`, `privatePilot=true`.
- 자동전송이 기록되었고 현재 웹 MD 응답을 기다린다. 응답 후 같은 작업이 원본 전용 지도·포인트 추출과 출제 검수·게시로 이어진다.
- 기존 Main-Quiz의 build `c7fbb80dee4540a1`, 69문항 및 은행·검증·검수 지문이 배포 전 기준과 동일한 것을 확인했다.
- 상태·원본 지문: `pilot-status.json`. 운영 화면: `production-dispatched.jpg`.

2026-11-03 20:12 KST 최종 확인: `held / ChatGPT 응답 대기`, dispatched=true, received=false, published=false. 실제 웹 MD가 아직 반환되지 않아 실제 자료의 검수·게시 완료는 미확인이다. 재전송·횟수 초기화·ChatGPT 직접 접속은 하지 않았다. 기존 은행의 build/status/69문항/은행·검증·검수 지문 모두 기준과 동일하다. 실제 화면에도 같은 응답 대기가 표시된다. 러너와 브라우저 탭을 유지했다.

진행 중인 시범의 게시 성공을 아직 선언하지 않는다. 후속 확인에서는 위 generation/job을 조회하고, 완료된 원문과 ledger를 그대로 이어 사용해야 한다.

## 21:15 KST 후속 확인
웹 응답은 수신됐으나 블럭 범위 보류 및 normalize의 생성 전 형식 거절을 확인해 각각 root-explicit-job-scope와 root-schema-compat에서 수정·검증했다. 동일 generation/job/원본/웹 응답을 유지했다. 실패 원장과 로그를 보존한 한 번의 기술 복구 후 현재 normalize 준비가 running이다. 최종 검수/게시 완료는 아직 미확인이다. 상세는 두 후속 작업 기록과 pilot-status.json에 있다.
