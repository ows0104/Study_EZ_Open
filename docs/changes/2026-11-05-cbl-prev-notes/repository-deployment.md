# 저장소 통합·운영 배포 완료

2026-11-05 사용자 ‘일단 여기까지 커밋, 푸시하고 배포하자.’ 승인에 따라 [PR #5](https://github.com/ows0104/Study_EZ_Open/pull/5)를 병합하고 API·웹 배포 및 사후 확인을 완료했다.

- PR head: `96b89d14170ffdf00ebec9a38968611301bce01f`, [검사 성공](https://github.com/ows0104/Study_EZ_Open/actions/runs/42034130138).
- 병합·운영 Git SHA: `5c56d462078527470221b2722ba81e15db512a7c`, [병합본 검사·API 배포 성공](https://github.com/ows0104/Study_EZ_Open/actions/runs/42035532298).
- 양쪽 검사에서 일반 Python 1,936 passed / 기존 skip 1, 독립 GUI 12 + 2 passed, 서버 108개 파일 전부 통과, 웹 타입·빌드 통과, Node/bridge/배포 경계 95개 통과.
- API revision `studyez-api-release-420355322981`, 트래픽 100%, health Git SHA 일치, 무인증 보호 경로 401 확인. 서버 산출물 해시 `255d26ac76c2af1c13bdda68462aee50876d9884775d371728fecfb90d5a5dad`는 직전 기능 런타임과 동일하다.
- Pages production 배포 `946eac88-f4e2-4d51-bbed-89154c25c1fb`, Git `5c56d46`, success 및 `studyez.kr` alias를 실제 대시보드에서 확인했다. 2026-11-05 22:37 KST에 게시 완료됐으며 Retry는 필요하지 않았다.

CBL 세 대상 261118_03·261125_07·261126_07은 배포 후에도 2025년 자료, 기존 선택 fingerprint, attachmentNeedsReview=false를 유지했다. 세 저장 객체의 존재/크기 및 로컬 원본 SHA-256을 확인했다. 로그인한 운영 화면에서도 암면역 CBL에 2025년 성승용 필기와 CBL예습참고 PDF 버튼이 표시되는 것을 확인했다. 로컬 실제 매핑 파일은 병합된 Git 버전과 바이트가 동일하다.

이번 저장소 통합/배포에서는 자료·선택 메타데이터·학습 기록·스키마·권한·비밀값을 다시 변경하지 않았다. 원본 PDF와 비공개 스냅샷도 커밋하지 않았다. 이전에 완료한 자료 연결의 검증/보존 결과는 [자료 반영 기록](deployment.md)을 따른다.

직전 API revision은 `studyez-api-release-420075543911`(Git `c86e15fb`), Pages 성공 배포는 `8ecb4ab7-8580-4b14-ab66-6f2ccebff47a`다. 필요시 이 코드/웹 버전으로 복원하며 이미 확인한 CBL 자료 연결과 학습 기록은 되돌리지 않는다. 실제 Actions 배포 영수증, health/401, Pages 목록, CBL 사후 확인과 화면은 `runs/_development/2026-11-05-cbl-prev-notes/repository-release/`에 보존한다. 수동 후보 배포를 실행한 것처럼 기록하지 않는다.
