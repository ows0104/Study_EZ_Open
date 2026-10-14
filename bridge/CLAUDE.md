# bridge 작업 안내

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

개발·다운로드 ZIP은 `../web/scripts/pack-extension.mjs`,
스토어 ZIP은 `build-store-package.ps1`로 만든다.
스토어 게시 여부는 소스 버전으로 추정하지 말고 실제 게시 상태를 확인한다.
