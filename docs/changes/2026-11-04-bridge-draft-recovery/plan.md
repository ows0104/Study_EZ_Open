# 기본 링크 버튼 및 GPT 브리지 이전 초안 충돌 복구 — 구현 계획

## 변경 범위·대상 파일·순서
1. web/src/calendar/PreviewAction.tsx의 예습 기본 링크 만들기 span을 실제 button으로 바꾸고 start("shared", false)를 연결한다. 필기 없음/진행 중/브리지 호환 조건과 관리자 권한을 유지한다. 자동전송 도구와 기존 공유 링크 열기·교체 확인 동작은 유지한다. BankPanel 제품 코드는 수정하지 않는다.
2. bridge/chatgpt-bridge.js와 bridge/background.js에 전송 전 초안의 소유/내용 지문을 확인하는 최소 상태를 연결한다. 확인된 이전 브리지 초안만 자동 정리한다. 출처 불명 초안은 팝업의 명시적 입력창 정리 선택으로 복구하며, 선택 시 초안·첨부가 바뀌지 않았는지 다시 검사한다. 알 수 없는 첨부를 무조건 제거하지 않는다.
3. 전송 전 충돌과 전송 후 접수 불확실 상태를 분리한다. 취소/수정/화면 이동은 계속 중지하며, 이미 누른 전송은 다시 누르지 않는다.
4. tests/bridge/test_autosend.cjs, test_link_recovery.cjs와 새 web/tests/preview-actions.test.cjs에 관련 회귀를 추가/갱신한다. 스크린샷처럼 이전 강의 프롬프트가 남은 상태에서 다른 강의를 요청한 경우를 포함한다. test_web_versions.cjs의 기존 rootWeb mock 누락은 실제 코드 변경 없이 테스트 의존성만 현행 인터페이스에 맞춘다.
5. bridge/manifest.json 버전과 bridge/README.md, 필요한 web/src/notices/GuidePage.tsx의 복구 안내를 맞춘다. ZIP은 기존 web build 경로로 생성한다. 다른 작업의 미커밋 변경은 유지한다.

## 검사 명령과 성공 조건
모든 명령은 저장소 루트에서 scripts/development.py verify로 기록한다. Python 실행기는 server/.venv/Scripts/python.exe를 사용한다.

- bridge: node --test tests/bridge/test_autosend.cjs tests/bridge/test_link_recovery.cjs tests/bridge/test_web_versions.cjs tests/bridge/test_bank_file.cjs tests/bridge/test_bank_download.cjs
- web-links: node --test web/tests/preview-actions.test.cjs
- web-types: npm --prefix web run typecheck
- web-build: npm --prefix web run build

전송 전 모의 GPT 입력창에서 동일 초안, 다른 버전의 이전 초안, 사용자 작성 내용, 알 수 없는 첨부, 복구 직전 수정, 취소, 직접전송, 자동전송 1회, 전송 후 불확실 상태를 확인한다. 외부 GPT에 실제 자료를 전송하지 않는다. 승인 전 기준 검사에서 브리지 67개 중 66개 통과, 1개는 test_web_versions.cjs의 rootWeb mock 누락으로 실패했다. 이는 수정 후 통과 근거가 아니다.

## 위험·복원·승인할 범위
승인 대상은 위 예습 기본 링크 카드 클릭 연결 및 ChatGPT 입력 브리지 초안 복구의 로컬 구현·회귀 검사·확장 ZIP 생성이다. 운영 배포·확장 설치/사용자 데이터 정리·실제 자료 자동전송은 별도 범위다. 가장 큰 위험은 사용자 초안 오인과 중복 전송이므로 자동 정리는 지문으로 확인된 미변경 미전송 초안에 한정하고 나머지는 팝업에서 사용자가 명시적으로 선택한다. 되돌릴 때는 이 작업의 패치만 복원하며 다른 작업의 변경과 모든 실제 기록을 유지한다. 사용자의 제보·위치 설명·스크린샷만으로 build 승인을 기록하지 않는다.
