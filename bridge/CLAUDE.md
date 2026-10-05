# bridge 작업 안내

PDF를 AI 대화에 붙이고 예습 링크 또는 Quiz Bank 답 본문을 회수하는 Chrome 확장이다.

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

`mode: "bank"`는 관리자용 답 본문 회수다.
`answerText` → `STUDYEZ_BANK_ANSWER` → 웹 저장 흐름을 유지하고,
이 대화 주소를 예습 링크로 저장하지 않는다.

개발·다운로드 ZIP은 `../web/scripts/pack-extension.mjs`,
스토어 ZIP은 `build-store-package.ps1`로 만든다.
스토어 게시 여부는 소스 버전으로 추정하지 말고 실제 게시 상태를 확인한다.
