# 요구사항과 설계

- Spotter는 현역 형제 앱이다. 자체 소스/데이터/검사는 그대로 유지하고 기본 검색 범위에서 분리한다.
- 공유 API·인증·계정·세션과 bridge/예습/기존 Main 읽기 경로는 현역이므로 이동하지 않는다.
- 보관 대상: 완료 상태가 기록된 과거 release 사본 12개, local-test 코드의 임시 test.db 폴더 125개.
- 대상 파일 5670개, 171558613바이트, 외부 node_modules junction 12개.
- 원본: `C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open`. 목적지: `C:\Users\ows01\Documents\Python Scripts\Study_EZ_Archive\2026-10-26-independent-materials/tree/<원본 상대경로>`.
- 상세 선택 목록은 archive-index.json. 파일별 해시·junction 원래 목적지는 로컬 archive-manifest.json에 저장한다.
- 원본 runs/강의 자료/문항/검수/사용자 복구 데이터, 최신·미완료·Git 중첩 사본은 원위치 보존한다.
- 활성 소스/문서/예약 작업/자동화 참조 없음, Git 비추적 여부를 확인한다.
- 오래된 완료 기록은 당시 근거이며 현재 운영 버전과 같다고 주장하지 않는다.
- 압축 백업 → 모든 파일 해시 확인 → 전체 파일 복원 시험 → 참조 안내 작성 → 동일 드라이브 이동 → 재검증.
- junction은 따라 복사하지 않고 원래 절대 목적지를 기록한다. 이동 전후 목적지와 원본 의존성 보존을 검사한다.
- 비밀 설정이 포함될 수 있으므로 보관 폴더와 압축본은 로컬 비공개이며 원격 업로드·Git 추가 금지.
