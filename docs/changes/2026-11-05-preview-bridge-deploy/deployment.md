# 운영 배포 완료 — 2026-11-05 KST

사용자 “운영 사이트에도 배포해줘”에 따라 앞서 승인한 예습 기본 링크 버튼 및 GPT 이전 초안 복구만 운영 웹·브리지 다운로드 ZIP에 반영했다.

- 이전 운영 Pages: `57fe6571-2415-4250-9895-e5f2bb903171`.
- 배포 고정 후보: `8f20afebae1d3e393dc6684c87025d310271e36cbff8e1cbac7b0d42e5ef75d8`.
- 실제 운영 Pages: `d7970ab3-67ef-4598-aaf5-8903bd268b1e` (study-ez-open/master).
- 실제 배포 attempt: `1793808157567703600`, 상태 succeeded.
- 2026-11-05 01:03 KST 사후 확인: healthy, smoke exit 0, passed=true.
- 공개 사이트: https://studyez.kr 및 https://study-ez-open.pages.dev.
- 고유 배포: https://d7970ab3.study-ez-open.pages.dev.
- 브리지: 1.3.21, https://studyez.kr/studyez-extension.zip.
- ZIP SHA-256: `6862ab44d364aeb4ba77697740f27863a393b5f698b92666d45699044741ab79`.

## 범위 및 실제 근거

운영 검증 사본의 재빌드가 이전 배포 후보의 전체 파일 manifest와 일치함을 먼저 확인했다. 그 위에 승인된 bridge·예습 카드·테스트·복구 안내·읽기 전용 smoke 13개 파일만 반영했다. GuidePage는 이번 안내 hunk만 바뀌었다. 다른 작업트리의 미배포 웹 기능은 섞지 않았다. 서버/API/DB/기존 대화·학습·검수·대기 응답과 시범 작업은 변경하지 않았다.

검사: bridge 92/92, 실제 Chrome 모의 화면 12/12, 웹/확장/서버 제공자·메시지·버전 계약 7/7, TypeScript 및 생산 빌드 통과. 최초 bridge 검사에서 테스트 fixture 복사 누락을 보완했고 기존 실패 기록은 유지했다. fixture 지문은 bank-file-valid.md `611f722240933085750a9e97937786cd89ed7c8a66b808bc01678e0d2f6ccaf7`, bank-file-cases.json `5b9f9076bf82adef8b7b2fbebb1e9c2ffc23be02fc32aa40379f230897594565`다.

사후 확인은 studyez.kr·pages.dev·고유 배포 URL의 HTML 및 브리지 ZIP을 고정 후보와 바이트 비교해 일치했다. 변경된 JS 번들 27개도 공개 CDN 파일과 일치했다. API health/CORS, 익명 및 잘못된 토큰의 timetable/spotter 보호 경로 401을 확인했다. 외부 GPT에 접속하거나 실제 강의 자료를 전송하지 않았다. 로그인한 실제 자료 생성·전송·링크 회수는 이 읽기 전용 배포 확인과 구분한다.

정본 실행 공간은 `tmp/preview-bridge-20261105`다. 해당 폴더의 docs/changes/2026-11-05-preview-bridge-deploy/state.json과 runs/_development/2026-11-05-preview-bridge-deploy/에 고정 후보·원격 업로드·사후 검사 영수증이 있다. 본 작업 폴더의 state.json 및 verified-scope/는 그 실행 근거 사본이며 현재 원 작업트리의 전체 소스를 검사한 것으로 해석하지 않는다.

## 사용 적용

사이트 버튼은 새로고침하면 새 버전이 표시된다. GPT 초안 복구는 브리지 ZIP을 1.3.21로 업데이트하고 chrome://extensions에서 확장을 다시 로드한 뒤 Study EZ·GPT 탭을 새로고침해야 한다. 사용자 기기의 확장 설치나 Chrome Web Store 게시를 실행한 것은 아니다. 알려진 실패 초안은 확인 후 복구하며, 구버전에서 남긴 초안 등 출처를 확인할 수 없으면 팝업의 ‘이전 초안 비우고 자동전송’ 또는 ‘이전 초안 비우고 자료 넣기’를 선택한다.
