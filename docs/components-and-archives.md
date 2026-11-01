# 제품 경계와 보관 자료

StudyEZ 작업은 web/server, 출제는 quizbank/quizgen/content, 연결부는 runner/bridge에서 시작한다.
공용 계약은 studyez_contracts, 로그인 세션 원본은 platform/session이다.

| 영역 | 판단과 위치 | 함께 확인할 연결 |
|---|---|---|
| Spotter | 별도 현역 앱. spotter/에 유지, 기본 검색에서 제외 | server/app/routes/spotter, 계정·권한·DB, platform/session, 별도 Pages/R2 배포 |
| bridge | StudyEZ 연결부로 유지 | web/scripts/pack-extension.mjs의 웹 빌드·확장 배포, 웹 응답 회수 |
| quizgen/예습/Anki | 현역·호환 영역으로 유지 | Pre-Quiz, 기존 덱 재빌드·다운로드, runner/deck 보조 함수 |
| 완료한 release 사본 | 외부 로컬 보관함으로 이동 | 부모의 완료 기록·패치·검사 로그는 원위치 유지 |
| 확인된 test.db 임시 폴더 | 외부 로컬 보관함으로 이동 | server/tests의 local-test tempfile 생산자 |
| runs와 나머지 work/out/tmp | 원위치 보존, 기본 검색 제외 | 수동 원문·검수·재개·복구·자료 매칭·미완료 작업 포함 |

독립 제품과 폐기 가능한 자료는 다르다. Spotter는 서버/계정/세션을 공유하므로
현재 단계에서 별도 저장소로 옮기거나 서버 라우트를 제거하지 않는다.
기존 Main 생성 코드도 기존 덱·예습·Anki와 보조 함수를 공유해 통째로 보관할 수 없다.
out/_bundle, out/_image_check, schema, 점수·실험 결과도 이번에는 보존한다.
나이·용량·이름만으로 불필요하다고 판정하지 않는다.

## 관련 부분만 읽기

- 사이트: `rg <검색어> web/src server/app`
- 출제: `rg <검색어> quizbank quizgen content/prompts`
- 연결부: `rg <검색어> runner bridge studyez_contracts`
- Spotter: `rg --no-ignore <검색어> spotter/scripts spotter/web`
- 수동 데이터: spotter/CLAUDE.md에 적힌 파일을 개별 지정한다.
- 과거 자료: 보관 색인에서 필요한 항목 하나를 골라 읽는다.

.ignore는 검색 범위만 바꾼다. Git 추적·빌드·배포·기능을 변경하지 않는다.

## 실제 보관과 복원

로컬 보관함은 원본 저장소 옆 `../Study_EZ_Archive/2026-10-26-independent-materials/`다.
`tree/` 아래에 원본 상대 경로를 유지한다. `archive-manifest.json`은 파일별 해시·원위치·
보관 위치·링크 목적지를, `recovery.zip`은 링크 대상의 내용을 제외한 파일 백업을 보관한다.
원본의 `work/ARCHIVED-2026-10-26.md`와 `tmp/ARCHIVED-2026-10-26.md`에서 찾을 수 있다.

완료된 옛 release의 부모 prepare/verify 스크립트는 과거 기록이다. 현재 운영 명령으로
재실행하지 않는다. 당시 경로가 필요하면 먼저 보관본을 복원하고 환경·승인을 확인한다.
부모 파일과 과거 docs/changes의 당시 기록은 원문을 유지한다.

복원: 보관함의 README와 restore.ps1을 사용한다. 해시와 링크를 확인하고 원위치가
비어 있을 때만 해당 폴더 하나를 이동한다. 같은 이름이 이미 있으면 덮어쓰지 않는다.
폴더 링크는 현재 web/node_modules를 가리키는 외부 의존성이다. 보관본을 독립 실행할 수
있는 전체 환경이라고 간주하지 않으며, 링크 대상이나 비밀 설정을 공개 저장소에 올리지 않는다.

이번 목록과 검사 결과: [P4 기록](changes/2026-10-26-independent-materials/).
