# Bridge 기본 텍스트 교체 — Implementation Plan

현재 사용자가 기존 프롬프트를 기본 비우고 이번 프롬프트를 넣으라고 구체적으로 지시했다. 이 범위로 승인 기록과 build gate를 확인하고 구현한다.

1. bridge/chatgpt-bridge.js의 checkDraft에서 텍스트 충돌 중지를 제거한다. 실제 입력은 기존 텍스트 삭제 후 현재 프롬프트 입력/확인으로 처리한다. 스냅샷 비교·첨부 소유 확인·중간 사용자 수정·취소·이동 및 전송 1회 규칙은 유지한다.
2. tests/bridge/test_autosend.cjs와 web/tests/preview-actions.test.cjs, tests/bridge/autosend-browser.html의 이전 텍스트 충돌 기대를 새 기본 동작으로 맞춘다. 텍스트 교체·빈 입력·같은 프롬프트·직접전송·자동전송·첨부 경계·다운로드 중 수정·취소를 실제 모의 Chrome에서 확인한다.
3. bridge/manifest.json/protocol.js를 1.3.22로 맞추고 README/PRIVACY 관련 문구를 갱신한다. web/scripts/pack-extension.mjs로 로컬 ZIP을 만든다. 운영 웹/서버 배포·확장 설치는 하지 않는다.
4. development.py verify로 bridge(Node 전체 및 Python tests/bridge), browser(격리 Vite+Chrome preview-actions), package(ZIP 생성 및 소스 바이트 대조)를 기록한다. 자체 코드 리뷰와 release gate를 확인하고 산출물/설치 적용 조건을 안내한다.

되돌림은 이 작업의 변경만 복원하며 이전 미커밋 작업과 실제 데이터는 건드리지 않는다. 권한/공개범위/전송 동의를 확장하지 않는다.

검사 지문은 실제 브리지 코드와 web/tests 모의 화면을 함께 포함하도록 site 영역으로 기록한다. bridge-python 검사는 .venv/Scripts/python.exe -m pytest tests/bridge -q --basetemp=tmp/bridge-py-final-1105다. Gemini 모의 화면은 기존 Gemini 업로드 준비 메시지/메뉴도 제공한다. 변경은 같은 승인 동작의 검증 구체화다.
