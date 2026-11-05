# 승인 전 진단

## 스크린샷으로 확정한 범위

- 팝업 제목은 Study EZ 예습 자료이고 공개 공유 링크 모드다. 문제은행 화면이 아니다.
- 이번 요청은 [251106_07] 심내막염으로 시작하며, 입력창에는 [251106_06] 무산소성세균 파일명과 이전 예습 프롬프트가 남아 있다. 파일명은 입력 텍스트로 보이며 실제 PDF 첨부 여부는 이 사진만으로 판단하지 않는다.
- 실제 오류 문구: “입력창에 작성 중인 다른 내용이 있어 자동 진행을 멈췄습니다. 새 대화로 다시 시작해 주세요.”
- 예습 기본 링크 만들기는 web/src/calendar/PreviewAction.tsx에서 span으로 그려지고 onClick이 없다. 자동전송 도구에는 start("shared", automatic)이 있으므로 두 동작의 차이가 제보와 일치한다.
- 아래 최초 BankPanel 조사 결과는 참고이며 이번 버튼의 확정 원인이 아니다. 구현 대상은 PreviewAction과 공통 ChatGPT 입력 브리지로 정정했다.

## 최초 조사

- 사용자 확인: 충돌은 Study EZ 서버 오류가 아니라 GPT 내부 Bridge 팝업에 표시됨.
- 기본 링크 만들기 버튼: web/src/bank/BankPanel.tsx의 disabled 조건에 extensionCompatible가 포함됨. make()에는 setShowSetup/setError가 있지만 비활성 버튼은 해당 분기에 들어갈 수 없음. 설치 버전은 아직 미확인.
- 초안 충돌: bridge/chatgpt-bridge.js의 reusableDraft는 빈 입력 또는 이번 프롬프트와 동일한 입력만 허용함. 다른 내용이면 start()가 예외를 내고 catch에서 confirm.hidden=true로 복구 동작을 제거함. 이전 실패 요청의 프롬프트 버전이 바뀌어도 같은 경로에 해당할 수 있음. 실제 오류 문구는 아직 미확인.
- 기준 검사: node --test tests/bridge/test_autosend.cjs tests/bridge/test_web_versions.cjs tests/bridge/test_link_recovery.cjs → 67개 중 66 통과/1 실패. 실패는 기존 test_web_versions.cjs의 rootWeb 의존성 mock 누락(TypeError webGenerationId).
- 구현·운영 데이터 변경·외부 GPT 전송은 실행하지 않음. scripts/development.py로 작업을 생성하고 intent/spec/plan만 작성함.
