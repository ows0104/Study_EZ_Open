# 브리지 스토어 ZIP 복구 (2026-11-10)

## 의도

복습 개인 링크를 만들 때 확장 확인 카드가 「Study EZ 예습 자료」로 뜬다. 사용자 브리지를 갱신한다.

## 진단

- 사용자 크롬 기본 프로필의 브리지는 웹스토어 공개판 1.2.0이다(`Secure Preferences` 확인).
- 1.2.0 `chatgpt-bridge.js`는 제목을 `bank ? "Study EZ Quiz Bank" : "Study EZ 예습 자료"`로 고정한다.
  사이트는 1.3.5 미만에 복습 요청을 `mode: "personal"`로 보내 저장 위치만 구분하므로 제목은 바꿀 수 없다.
- 현재 소스(1.3.16부터)는 `mode: "review"`이면 「Study EZ 복습 자료」를 표시한다. 사이트·확장 코드 수정은 필요 없다.
- 고치려면 스토어 공개판을 갱신해야 한다. 그런데 `build-store-package.ps1`과 `audit-store-package.py`의
  파일 목록이 1.3.19·1.3.20에 추가된 `bank-file.js`·`bank-download.js`를 빠뜨렸다. `background.js`가
  `importScripts`로 둘을 읽으므로 그 ZIP을 올리면 서비스 워커가 시작하지 못해 확장 전체가 멈춘다.
- 권한은 1.2.0과 같다(`storage`, `scripting`, 같은 호스트). 갱신해도 크롬이 확장을 비활성화하지 않는다.

## 변경

- 스토어 ZIP에 두 파일을 넣는다. 빌드·감사 둘 다 `importScripts`·`content_scripts` 참조를 ZIP과 대조해 다시 빠지면 실패한다.
- 확장 소스·버전·사이트는 바꾸지 않았다.

## 검사

- `bridge/build-store-package.ps1` → `studyez-preview-bridge-1.3.23-web-store.zip`, 13개 항목.
- `audit-store-package.py` 통과. 패키지 JS 전부 `node --check` 통과. `pytest tests/bridge` 9개 통과.

## 남은 일 (사용자)

1. Chrome Web Store 개발자 대시보드에 1.3.23 ZIP을 올리고 심사를 제출한다.
2. 실제 공개를 확인한 뒤 Pages 빌드 변수 `VITE_EXTENSION_STORE_VERSION`을 1.3.23으로 바꾸고 웹을 다시 빌드한다.
3. 공개 전에 기본 프로필에서 바로 쓰려면 스토어판 1.2.0을 먼저 제거하고 개발자 모드로 `bridge` 폴더를 로드한다.
   둘을 같이 두면 두 확장의 콘텐츠 스크립트가 같은 사이트 요청에 함께 응답할 수 있다.
