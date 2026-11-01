# 분류 근거

Spotter는 server/app/main.py에 API가 등록되어 있고 계정/권한/DB, 공용 session.js를 공유한다.
bridge는 web/package.json과 pack-extension.mjs가 웹 빌드에 포함한다. quizgen은 예습·기존 덱·
Anki와 runner/deck의 보조 코드에 연결된다. 이들을 오래된 이름이나 독립 UI라는 이유로 제거하지 않았다.

work 163개 직계 항목(디렉터리 157개), tmp 358개, out 60개와 Spotter/자료/캐시를
파일 목록·크기·링크 수준으로 조사했다. 이는 모든 문항 내용을 읽거나 삭제 가능성을 보증한 검사가 아니다.
classification.json에 항목별 실제 처분과 보존 이유를 기록했다.

보관한 release 12개는 2026-10-16 작업의 release.json에 complete가 남아 있는 과거 사본이다.
현재 운영 서버와의 동일성을 뜻하지 않는다. 최신/미완료/중첩 Git 사본은 유지했다.
부모의 패치와 완료 기록·검사 로그는 유지하며, 다른 작업 기록에서 찾은 문자열 일치는
이전 배포 revision 이름 또는 Git branch 이름으로 실제 release 경로 참조가 아니었다.

보관한 임시 DB 125개는 server/tests에서 local-test 설정과 tempfile.mkdtemp(prefix=...)로
test.db를 생성하는 코드를 확인했고, 해당 폴더에 test.db 하나만 있음을 확인했다.
사용자 학습 DB와 원본 runs를 읽거나 이동하지 않았다.

Git 조회 결과 work/tmp/out에는 추적 파일이 없었다. 현재 소스·문서(과거 변경 목록 제외)·
Codex 자동화 설정에는 선정 경로 참조가 없었다. StudyEZ Agent 예약 작업은 scripts/agent.ps1을
실행하며 선정 경로를 사용하지 않는다. 이동 직전 프로젝트를 사용하는 외부 프로세스가 없음을 확인했다.
과거 docs/changes의 후보 목록은 당시 기록으로 유지하고 현재 보관 색인으로 연결했다.

Windows junction 12개는 현재 web/node_modules를 가리킨다. 링크 대상 파일을 복사·이동하지 않았다.
이동 도중 명령 출력 과다로 작업이 중단되어, 양쪽 경로·해시를 다시 확인하고 남은 항목만
이어 이동했다. 최종 137개 전부의 파일·디렉터리·링크 대조가 통과했고 이동 로그가 남아 있다.
