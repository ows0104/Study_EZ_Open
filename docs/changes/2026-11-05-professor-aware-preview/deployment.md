# 운영 반영 완료 — 2026-11-05

사용자 “반영해줘.” 승인에 따라 실제 운영에 반영하고 사후 확인을 완료했다. 구현·운영 범위와 보존 조건은 [승인 기록](deployment-authorization.md)을 따른다.

## 고정 버전과 배포 근거

- [PR #3](https://github.com/ows0104/Study_EZ_Open/pull/3), 최종 head `1bc7ce9ecd3bf0eecad3a661d251ec834013f50b`의 [검사](https://github.com/ows0104/Study_EZ_Open/actions/runs/42005752712) 통과 후 병합.
- 운영 Git SHA: `c86e15fbfd7404255c66bbb30e4ccf74fe2f952b`. 동시에 병합된 기존 deck 수정과 협업 문서를 포함한 최종 병합본의 [전체 검사·배포](https://github.com/ows0104/Study_EZ_Open/actions/runs/42007554391)도 성공했다.
- 병합본 검사: 일반 Python 1,936 passed, 기존 skip 1; GUI 12 + 2 passed; 독립 서버 108개 파일 전부 통과; 웹 타입·빌드 통과; Node/bridge/배포 경계 95개 통과. 로컬 기능 브라우저 검사 4개도 앞서 통과했다.
- API revision `studyez-api-release-420075543911`, 후보 해시 `255d26ac76c2af1c13bdda68462aee50876d9884775d371728fecfb90d5a5dad`. 운영 health SHA 일치, 보호 경로 무인증 401, 명시한 revision에 트래픽 100%.
- Pages production 배포 `8ecb4ab7-8580-4b14-ab66-6f2ccebff47a`, 같은 SHA `c86e15f`, 대시보드 success 및 `studyez.kr` alias 확인. 서버 준비 대기 후 정상 게시됐으며 Retry는 필요하지 않았다.

## 실제 자료·DB 반영

- 단일 nullable `lecture.preview_source JSON` 칼럼만 추가했다. 다른 스키마·권한·비밀값 변경 없음.
- 감염과 면역의 기존 84개 강의 ID를 유지하고 선택 메타데이터만 적용했다. 제목·교수·UID·시간표 연결 등 기존 식별 필드는 그대로다. 기존 중복 ID도 합치거나 삭제하지 않았다.
- 교수 변경 11개, 보유 자료 기준 신규 교수 4개. 확인 필요 24개는 앞의 태그와 중복될 수 있다. 확인 불가능한 담당·합본·분반·누락 자료는 추측으로 확정하지 않았다.
- 예습 원본 72개를 확인했다. 8개는 같은 교수의 2022~2023년 자료이며, 최종 운영 대조 결과 72개 모두 이미 해당 파일이 연결되어 있었다. 실제 첨부 업로드/교체는 0개이고 기존 객체를 유지했다. 단순히 작년 대응과 다른 후보 8개를 새 교체 8개로 집계하지 않는다.
- PDF 72개 약 743MB를 저장소에서 읽어 선택 원본 SHA-256과 실제 바이트 일치를 확인했다. 원본 파일·기존 대화·덱은 자동 재생성하지 않았다.
- 적용 전후 `preview`, `user_preview`, `user_review`, `pre_item`, `main_item`, `quiz_bank`, `bank_state`, `quiz_attempt`, `main_attempt`, `card_edit` 10개 과목 범위 테이블의 전체 스냅샷이 일치했다.
- 배포 직전 전체 일시정지 상태는 false였고, 작업 후 동일한 기존 상태와 개별 선택을 복원했다.

## 실제 화면 확인

로그인한 운영 사이트에서 읽기 전용으로 확인했다. 생성·풀이·파일 열기·대화 수정 버튼은 누르지 않았다.

- 사슬알균: 교수 변경, 2025년 김현제 → 2026년 김범준, 2023년 김범준 예습 필기 및 실제 2023 PDF 이름 확인.
- 두드러기/혈관부종/아나필락시스: 교수 변경 + 신규 교수, 올해 강성윤(시간표 기준 잠정), 최근 5년 동일 교수 자료 없음, 2025년 장윤석 필기 대체와 실제 파일명 확인.
- 누락·담당 충돌은 확인 필요, 미보유 2024년과 2021년 일부 파일 확인 필요 범위가 화면에 나타나는 것 확인.
- 운영 증거 화면: `out/professor-tests/live/same-professor.png`, `new-professor-fallback.png` (로컬 보관).

비공개 원상 스냅샷과 실제 영수증은 `runs/_development/2026-11-05-professor-aware-preview/`에 보존한다. 원본·공유/개인 대화 주소·학습 내용·인증정보는 Git에 넣지 않는다. 자동 배포의 SHA별 검사/배포 영수증은 Actions에 보존하며, 수동 후보 절차의 미실행 단계를 성공으로 기록하지 않는다.

## 관측과 복원

직전 API는 `studyez-api-release-420036152591`(Git `d5e30590f138dddfe112f30176f7520a9d63ebdb`), 직전 성공 Pages는 `0d52780a-db50-4fcf-99ed-b34bb009238c`였다. 최초 준비 이후 다른 승인 작업이 배포됐기 때문에 실제 직전 버전을 별도로 보존했다.

필요시 러너 일시정지 후 해당 API 트래픽과 Pages 성공 배포로 복원한다. 메타데이터 원상은 `metadata-before.json`, 원본 객체는 그대로 보존되어 있다. 학습 기록·대화·추가 JSON 칼럼은 삭제하지 않는다. 이후 교수/시간표·필기가 바뀌면 같은 선택 기준을 다시 적용하고, 출처가 달라진 예습 대화는 자동 재귀속하지 않는다.
