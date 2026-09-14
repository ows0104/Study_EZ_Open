# bridge — 예습링크 크롬 확장

작년 필기를 AI 새 대화에 채우고, 생긴 대화 링크를 회수해 서버에 적는다.

    무엇을 고치면 어느 파일인가    ../docs/map.md §2
    검사                          pytest tests/bridge      4개
    스토어 제출                    ../docs/chrome-web-store-submission.md
    권한 · 어디서나 미는 함정       ../CLAUDE.md

**혼자 고쳐지는 일이 드물다.** 세 자리를 같이 본다.

    bridge/                      확장. manifest · background.js · provider-share.js
    ../server/app/preview_links.py   서버 쪽 짝. 경로 2개
    ../web/src/bridge/               사이트에서 확장을 잡는 자리

`tests/bridge/test_extension_providers.py` 가 **`server/app` 을 import 하는 유일한
검사다.** 확장과 서버가 같은 제공자 목록을 보는지 재기 때문이다 — 갈라지면 링크가
조용히 안 붙는다.

확장 zip 은 `web/` 이 싼다(`../web/scripts/pack-extension.mjs`). `npm run dev` 가
매번 돌리므로 **고친 것이 사이트 개발 서버에는 저절로 반영된다.** 스토어에 올리는
것은 `build-store-package.ps1` 이고 `audit-store-package.py` 가 그것을 본다.
