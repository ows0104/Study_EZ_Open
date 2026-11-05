# bridge 작업 안내

프롬프트 1.80부터 새 결과는 순수 JSON(schema_version=2) 파일이다. `bank-file.js`가 문항/근거/보기/충돌/완료 boolean을 검증하며 기존 MD도 계속 읽는다. JSON 자동 회수에는 확장 1.3.23 이상이 필요하다. 파일명은 요청 판에 따라 선택하며 실제 다운로드 버튼/공개된 링크만 사용한다. 구조 통과를 의학 검수 완료로 표시하지 않는다.

PDF를 AI 대화에 붙이고 예습·복습·문제은행 링크를 회수하는 Chrome 확장이다.

| 책임 | 파일 |
|---|---|
| 확장 권한·연결 | `manifest.json`, `background.js` |
| ChatGPT 링크·답 본문 | `chatgpt-share.js` |
| 다른 제공자 | 해당 `*-share.js` |
| 서버 링크 검증 | `../server/app/preview_links.py` |
| 사이트 연결 | `../web/src/bridge/`, `../web/src/bank/bankBridge.ts` |

검사: `python -m pytest tests/bridge`.
설치·동작 안내는 [README](README.md), 스토어 제출은
[제출 문서](../docs/chrome-web-store-submission.md)를 본다.

제공자 목록은 확장과 서버가 같아야 한다. 대응 검사는
`tests/bridge/test_extension_providers.py`가 담당한다.

`mode: "bank"`는 관리자용 문제은행 링크 생성이다. 공유·개인 주소는
`chatgpt_bank_share`·`chatgpt_bank`로 각각 전달하고 `/bank/links`에 저장한다.
완료 표시가 마지막 줄에 있는 문항 본문은 `/bank-response`로 전달해 CLI 검수·보완·게시를 시작한다. 링크는 예습 링크 자리를 덮지 않는다. 저장 확인 전에는 본문을 보관·재전달한다.

프롬프트 1.78부터 모든 강의의 전체 결과를 실제 UTF-8 `.md` 파일로 받는다.
`bank-file.js`는 과목·강의 ID·버전·문항·정답 참조·완료 표식·해시를 검증한다.
답변에 노출된 직접 다운로드 주소만 읽고, sandbox 링크를 읽을 수 없으면 실제 파일 선택을 안내한다.
수집 확장의 최소 버전은 1.3.19다. 검증된 파일 원문은 공유 대화 본문으로 덮어쓰지 않는다.

## 실제 MD 자동 회수 (1.3.20)

일반 링크 외에 해당 파일 카드의 실제 다운로드 버튼도 처리한다. `bank-download.js`는
그 버튼이 생성한 Blob 원문만 받고 과목·강의·버전이 맞는 MD만 전달한다. API 주소를 추측하지 않는다.
별도 다운로드 권한은 추가하지 않는다. Study EZ의 서버 저장 확인 전에는 공유 링크를 내보내지 않는다.
파일이 없거나 서버 저장이 실패하면 본문 수집으로 우회하지 않고 파일 전달을 재시도한다.

개발·다운로드 ZIP은 `../web/scripts/pack-extension.mjs`,
스토어 ZIP은 `build-store-package.ps1`로 만든다.
스토어 게시 여부는 소스 버전으로 추정하지 말고 실제 게시 상태를 확인한다.
