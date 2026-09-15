# web — studyez.kr 프론트

Vite + React + TypeScript. **이 폴더는 화면만 든다** — 파이프라인을 부르지 않고
`runner` 도 `quizgen` 도 모른다. 서버 경로 19개만 부른다.

    무엇을 고치면 어느 파일인가    ../docs/map.md §2
    검사                          cd web && npm run typecheck
    서버와의 계약                  ../server/CLAUDE.md
    권한 · 어디서나 미는 함정       ../CLAUDE.md

    src/calendar/   2,355줄   달력
    src/admin/      1,161줄   관리 화면
    src/lecture/      818줄   문제 푸는 화면
    src/styles/     3,435줄   색·여백
    src/bundle/       675줄   덱 여럿을 한 .apkg 로 — 여기서 합친다
    src/types.ts              화면을 고칠 때 거의 항상 같이 본다

**풀이 화면은 자기채점 자유회상이다.** 땡시(`../spotter/`)는 시간 재는 다지선다이고
**다른 제품이다** — 한쪽을 고칠 때 다른 쪽을 볼 일이 없다.

`src/supabase.ts` 가 `../platform/session/session.js` 를 import 한다. 저장소에서
둘이 정말 같이 쓰는 파일은 그것 하나다(땡시는 사본을 쓴다 — `../spotter/CLAUDE.md`).

## push 하면 이것만 배포된다

Cloudflare Pages 가 `web/` 을 보고 있어서 **프론트는 push 로 저절로 나간다.**
**API 는 안 나간다** — `server/deploy.ps1` 을 손으로 돌려야 한다. 둘을 같이 고쳤으면
서버를 먼저 올린다.

**반영됐는지는 로컬 해시로 재지 마라.** Pages 가 자기 환경에서 다시 빌드하므로
로컬 산출물의 해시와 배포된 것의 해시가 안 맞는다. 배포된 자산을 `pages.dev` 절대
URL 로 직접 받아서 본다. 자세한 것은 [../docs/cloudflare-pages-runbook.md](../docs/cloudflare-pages-runbook.md).

## 확장은 여기서 싸인다

`npm run dev` 와 `npm run build` 가 먼저 `scripts/pack-extension.mjs` 를 돌려
`../bridge/` 를 압축한다. 확장 자체를 고칠 때는 [../bridge/CLAUDE.md](../bridge/CLAUDE.md).
