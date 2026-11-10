# 브리지 스토어 사용자판 (2026-11-10)

## 의도

복습 개인 링크를 만들 때 확장 확인 카드가 「Study EZ 예습 자료」로 뜬다. 사용자 브리지를 갱신한다.
관리자 지시: 관리자가 쓰는 브리지를 그대로 스토어에 올리지 않는다. 학생용에서는 자동전송과 공유 링크를 뺀다.

## 진단

- 사용자 크롬 기본 프로필의 브리지는 웹스토어 공개판 1.2.0(커밋 `edd0b905`)이다(`Secure Preferences` 확인).
- 1.2.0 `chatgpt-bridge.js`는 제목을 `bank ? "Study EZ Quiz Bank" : "Study EZ 예습 자료"`로 고정한다.
  사이트는 1.3.5 미만에 복습 요청을 `mode: "personal"`로 보내 저장 위치만 구분하므로 제목은 사이트에서 못 바꾼다.
  현재 소스(1.3.16부터)는 `mode: "review"`이면 「Study EZ 복습 자료」를 표시한다.
- 사이트는 학생에게 `start("personal", false)`(예습)와 `autoSend: false` 복습만 요청한다.
  `shared`·`autoSend: true`·`bank`는 관리자 화면(`PreviewAction` 관리자 도구, `QuizCreateButton`, `rootWeb`)에서만 보낸다.
- 기존 스토어 빌드 스크립트는 1.3.19·1.3.20의 `importScripts`에 추가된 `bank-file.js`·`bank-download.js`를
  고려하지 않아, 그 ZIP은 서비스 워커가 시작하지 못한다.
- 권한은 1.2.0과 같다(`storage`, `scripting`, 같은 호스트). 갱신해도 크롬이 확장을 비활성화하지 않는다.

## 변경

- `protocol.js`에 `EDITION: "full"`, 버전 1.3.24. 관리자판 동작은 그대로다.
- `background.js`: `EDITION === "user"`이면 `shared`·`bank`·`autoSend: true` 요청을 「관리자용 브리지에서만」 오류로 거절한다.
  bank 다운로드 처리는 감시 모드를 먼저 확인한다(사용자판에는 bank 스크립트가 없다).
- `bridge/user-edition.mjs`(새 파일, 스토어·사이트 ZIP 공용): `EDITION`을 `user`로, `importScripts("protocol.js")`만 남기고
  manifest에서 `bank-file.js`를 빼고 bank 스크립트를 지운 뒤, 실행에 필요한 파일이 모두 있는지 대조한다.
  `build-store-package.ps1`은 localhost 제거 뒤 이것을 부른다.
- `audit-store-package.py`: 사용자판 표시·거절 분기·bank 스크립트 부재·참조 파일 대조·변환 결과 해시를 검사한다.
- `tests/bridge/test_store_edition.cjs`: 사용자판은 수동 예습·복습만 열고 나머지를 거절, 관리자판은 셋 다 연다.
- 스토어 등록표 문구에서 자동전송·공유 링크·Quiz Bank를 뺐다.
- 사이트 ZIP(`web/scripts/pack-extension.mjs`)도 사용자판으로 싼다. 변환은 `bridge/user-edition.mjs` 하나를
  스토어 스크립트와 같이 쓴다. 사이트 ZIP에서 개발 문서·스크립트(`CLAUDE.md`, 감사·빌드 스크립트)도 뺐다.
- 설치 안내(`ExtensionSetup`)는 관리자에게만 「관리자 기능은 저장소 `bridge` 폴더(관리자판)」를 덧붙인다.

## 검사

- 스토어 ZIP `studyez-preview-bridge-1.3.24-web-store.zip` 11개 항목, 감사 통과, 패키지 JS `node --check` 통과.
- 사이트 ZIP 13개 파일, bank 스크립트 없음, `EDITION: "user"`.
- `node --test tests/bridge/*.cjs` 119개, `pytest tests/bridge` 9개 통과.

## 남은 일 (사용자)

1. Chrome Web Store 개발자 대시보드에 1.3.24 사용자판 ZIP을 올리고, 등록표의 설명·단일 목적·권한·심사자 안내를
   [제출 문서](../../chrome-web-store-submission.md)대로 고쳐 심사를 제출한다.
2. 실제 공개를 확인한 뒤 Pages 빌드 변수 `VITE_EXTENSION_STORE_VERSION`을 1.3.24로 바꾸고 웹을 다시 빌드한다.
3. 관리자 크롬 기본 프로필에서 스토어판을 쓰지 않는다. 관리자판은 개발자 모드로 `bridge` 폴더를 로드한다.

## 알려진 한계

- 관리자가 사이트 ZIP이나 스토어판을 깔면 관리자 기능은 열리지 않는다. 관리자는 저장소 `bridge` 폴더를 로드한다.
- 스토어판 버전이 관리자 기능의 최소 버전을 넘으므로, 관리자가 스토어판만 깔린 크롬에서 관리자 기능을 누르면
  사이트는 스토어 설치를 안내하지 않고 확장의 「관리자용 브리지에서만」 오류를 보여 준다.
