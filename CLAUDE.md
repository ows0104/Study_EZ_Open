# StudyEZ 공통 작업 안내

## 작업 시작 대원칙 (모든 작업보다 먼저, 예외 없음)

두 사람이 여러 세션으로 동시에 작업한다. 새 기능·수정을 시작할 때마다 아래를 끝낸 뒤에만 파일을 고친다.

1. 기능 하나에 새 브랜치 하나를 최신 master(`origin/master`)에서 만든다. master에서 직접 작업하지 않는다.
   동시에 도는 세션은 각자 별도 worktree를 쓴다.
2. `git pull`로 대시보드(`dashboard` 브랜치의 `DASHBOARD.md`, 폴더 `../Study_EZ_dashboard`)를 최신으로 받는다.
3. 대시보드의 진행 중·예정 작업과 겹칠 여지(같은 파일·화면·API·DB·프롬프트)를 확인한다.
   있으면 시작하지 말고 사람에게 알려 조정한다.
4. 대시보드 "지금 하고 있는 작업"에 우선순위·작업·작업자/세션·브랜치·영역/파일을 쓰고 push한다.
   push가 거절되면 pull 후 3번부터 다시 한다.

끝나면(merge·중단) 대시보드에서 지운다. `dashboard`는 master에 merge하지 않는다.
명령과 세부 규칙: [협업 대원칙](docs/development/collaboration.md#작업-시작-대원칙-예외-없음).

StudyEZ의 모든 개발·유지보수는 [개발 루프](docs/development/README.md)를 따른다.
Intent → Spec → Implementation Plan → Build → Test → Review → Deploy → Maintain.
사람에게 따로 묻는 것은 되돌릴 수 없는 작업뿐이다([사람에게 묻는 것](docs/development/README.md#사람에게-묻는-것)).
그 밖에는 사용자의 작업 요청을 승인으로 보고 구현·검사·PR·병합·배포까지 진행한다.
이번 구조 정리만의 절차가 아니다. 새 작업은 docs/changes/<id>/에 기록한다.

## 읽기 순서

1. [작업 지도](docs/map.md)에서 사이트·출제·연결부·계약·독립 앱을 선택한다.
2. 관련 컴포넌트 CLAUDE.md, 계약, 수정 파일·검사를 읽는다.
3. 생성 데이터·work·과거 기록은 필요한 경로를 지정할 때만 읽는다.

## 경계

- 사이트: web, server. 서버는 로컬 생성기를 import하지 않는다.
- 출제: quizbank, quizgen, content/prompts. 현행 정책을 구조 정리를 이유로 바꾸지 않는다.
- 연결: runner, bridge. 생성기는 하위 프로세스, 사이트는 HTTP 계약으로 연결한다.
- 공용 검증: studyez_contracts. DB·서버·모델 실행에 의존하지 않는다.
- Spotter는 별도 현역 앱이며 인증·DB·세션 공유 의존성을 보존한다.

## 보존·승인

- 기존 문제·ID·학습 기록·개인 수정·제외 문항·검수 이력을 보존한다.
- 은행 교체·공용 문항 수정은 bank_retention을 거친다. ID만으로 학습도를 승계하지 않는다.
- server/.env는 운영 DB를 가리킬 수 있다. 검사에 격리된 로컬 DB와 저장소를 명시한다.
- runs에는 수동 원문·메모·HOLD·CHOSEN·자료 매칭·피드백이 있다. 재생성 캐시로 취급하지 않는다.
- 다른 작업의 미커밋 변경을 되돌리거나 커밋·배포에 섞지 않는다.
- 실패·대기·미실행은 성공과 구분한다. 기존 출제·검수 상한은 재실행으로 초기화하지 않는다.
- 현재 사용자의 명시적 승인을 적용한다. 이후 별개 작업에 대한 포괄 승인으로 확대하지 않는다.

## 적용 중인 개별 지시

족보 정리·첨부는 [공통 PDF 형식](docs/policies/jokbo-attachments.md)을 기본으로 한다.
연도별 교수 표시·올해 같은 교수 기출 우선·원문/그림 보존·실제 PDF 확인을 따른다.

문항 내용 변경·강의 재출제·자료 이동·검수 예외·수동 응답 처리는
[기존 사용자 지시 원문](docs/policies/pre-refactor-directions-2026-10-26.md)의 해당 강의/작업과
컴포넌트 안내를 반드시 확인한다. 원문을 보관한 것은 지시를 해제한 것이 아니다.
기본은 수동 웹 출제, 저장된 응답의 CLI 후처리, 원본·기록 보존이다.
진행 중인 예외는 범위·근거·종료 조건을 작업 폴더에 연결한다.

검사·배포: [명령](docs/commands.md), [배포](docs/deployment.md).
운영 관측·피드백: [개발 루프](docs/development/README.md), [피드백](docs/feedback-loop.md).
