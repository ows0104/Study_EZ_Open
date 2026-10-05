# web — studyez.kr 프론트

Vite + React + TypeScript. **이 폴더는 화면만 든다** — 파이프라인을 부르지 않고
`runner` 도 `quizgen` 도 모른다. 서버 경로 23개만 부른다.

    무엇을 고치면 어느 파일인가    ../docs/map.md §2
    검사                          cd web && npm run typecheck
    서버와의 계약                  ../server/CLAUDE.md
    권한 · 어디서나 미는 함정       ../CLAUDE.md

    src/calendar/   2,645줄   달력
    src/admin/      1,503줄   관리 화면
    src/lecture/    1,330줄   문제 푸는 화면
    src/styles/     3,836줄   색·여백
    src/bundle/       724줄   덱 여럿을 한 .apkg 로 — 여기서 합친다
    src/types.ts              화면을 고칠 때 거의 항상 같이 본다

**풀이 화면은 자기채점 자유회상이다.** 땡시(`../spotter/`)는 시간 재는 다지선다이고
**다른 제품이다** — 한쪽을 고칠 때 다른 쪽을 볼 일이 없다.

## 풀이 화면은 망각곡선으로 돈다 (2026-09-18)

**관리자 지시** — 「웹 퀴즈를 안키처럼 해줘. 망각곡선에 기반해서. 그리고 이전으로
돌아가는 기능도 만들어줘.」 그 전까지 이 화면은 카드를 한 줄로 훑고(`index+1/total`)
반복은 apkg 를 받아 간 사람의 안키가 들었다.

    Again·Hard·Good·Easy    찍으면 서버가 다음 때를 정한다
    되돌리기 (Z · Ctrl+Z)    찍기 전으로. 서버가 적어 둔 값으로 돌아간다
    몰아보기                 때를 무시하고 한 바퀴. 시험 전에 쓴다

**간격을 화면이 계산하지 않는다.** 정하는 곳은 서버의 `app/srs.py`(안키의 SM-2)
하나다. 버튼에 적는 「1분·10분·4일」까지 `reveal` 이 실어 보낸다(`next`). 여기서
다시 계산하면 사다리가 파이썬과 타입스크립트 두 곳에 산다.

    src/lecture/queue.ts    다음에 낼 카드를 고른다. **순수 함수다** — 화면 없이 읽힌다
    src/lecture/Quiz.tsx    카드를 그리고 넷을 받는다

**「0장」을 갈라서 그린다.** 카드가 없는 것과, 오늘 몫을 끝낸 것과, 몰아보기를 한
바퀴 돈 것은 다음에 할 일이 다르다(`queue.ts` 의 `EmptyReason`). 한 문구로 덮으면
사람이 고장으로 읽는다 — 루트 `CLAUDE.md` 의 함정 ③ 이 그것이다.

## 덱이 만들어지는 진행은 학생도 본다 (2026-09-21)

**관리자 지시** — 「퀴즈를 만들고 있을 때 관리자가 아닌 사용자도 사이드패널 현황을
볼 수 있게. 몇 단계 몇 분 남았는지.」 그 전까지 학생의 덱 칸은 파일 하나만 보고
그려서, **15분 뒤에 오면 되는 편과 아무도 안 만들고 있는 편이 똑같이 「아직
없습니다」였다.**

    src/calendar/DeckSlot.tsx   `DeckWatchSlot` 이 학생, `DeckMake` 가 관리자
    src/jobProgress.ts          줄을 짓는 곳. `watchLine` 이 학생 쪽이다

**줄을 두 벌로 짓는 이유는 할 수 있는 일이 달라서다.** 관리자의 줄은 진행 위에
「무엇을 해야 하는가」를 얹는다(노트북을 띄워라 · 다시 눌러도 소용없다). 학생은
그 어느 것도 못 하므로 그 말을 그대로 보여 주면 자기가 뭘 잘못한 줄 안다.

**부르는 경로가 다르다**(`GET /api/lectures/…/deck-job`). 관리자 경로를 열어 준
것이 아니다 — 저쪽은 남의 이메일까지 싣는다(`../server/CLAUDE.md`).

`src/supabase.ts` 가 `../platform/session/session.js` 를 import 한다. 저장소에서
둘이 정말 같이 쓰는 파일은 그것 하나다(땡시는 사본을 쓴다 — `../spotter/CLAUDE.md`).

## 공지사항 · 이용방법 (2026-10-04)

**관리자 지시** — 「슬슬 운영을 시작해서 공지사항하고 이용방법 탭을 만들어야할 것
같아.」 머리줄의 탭이 「관리」 하나에서 셋이 됐다.

    src/notices/NoticesPage.tsx   공지. 관리자는 같은 화면에서 쓰고 고치고 지운다
    src/notices/GuidePage.tsx     이용방법. **화면에 박은 고정 글이다**
    src/notices/seen.ts           「새 공지」 점 — 이 브라우저가 본 마지막 번호

**이용방법은 화면 문구를 옮겨 적은 글이다.** 버튼 이름·단축키·칸의 도형을 고치면
`GuidePage.tsx` 도 찾아 고친다 — 머리 주석에 어느 파일에서 옮겼는지 적혀 있다.

## Quiz Bank (2026-10-04)

**관리자 지시** — 「파일 직접 넣는 게 귀찮아. 우리 웹사이트에서 연결되게」 · 「공부까지 사이트로」.
ChatGPT 가 만든 문제은행을 사이트에서 만들고 푼다. Main-Quiz 옆에 나란히 선다.

    src/bank/bankPrompt.md   ChatGPT 에 가는 프롬프트의 **정본**. 머리 주석의 Version 을 올린다
    src/bank/BankPanel.tsx   캘린더 패널의 칸. 관리자 = 만들기·다시 정리·학생에게 열기
    src/bank/bankBridge.ts   확장이 가져온 답 본문을 서버에 저장한다(예습 링크와 같은 규칙)
    src/bank/BankStudy.tsx   /bank/:과목/:run 풀이 창. 형식 여덟 · 슬라이드 여러 장 · 외부지식 검토
    src/bank/ConceptMap.tsx  풀이 창 첫 화면 아래 개념 지도 — 관계 그래프 + 개념 카드. 숫자는 서버 엔진(`concept_map`)
    src/admin/BankReportTab.tsx   관리 「Quiz Bank 신고」. 학생의 「문제 있음」을 문항별로 — 고치는 곳은 아니다

**다음 문항을 화면이 고르지 않는다.** 서버의 `app/study_engine/` 이 숙련도·선행 문항·시험까지
남은 날로 고른다(`POST …/bank/next`). Main-Quiz 의 `queue.ts` 와 다르다 — 고르는 데 쓰는 값이
다 서버에 있다. **학생에게는 관리자가 연 은행만 보인다**(`open_to_students`).

## push 하면 이것만 배포된다

Cloudflare Pages 가 `web/` 을 보고 있어서 **프론트는 push 로 저절로 나간다.**
**API 는 안 나간다** — `server/deploy.ps1` 을 손으로 돌려야 한다. 둘을 같이 고쳤으면
서버를 먼저 올린다.

**반영됐는지는 로컬 해시로 재지 마라.** Pages 가 자기 환경에서 다시 빌드하므로
로컬 산출물의 해시와 배포된 것의 해시가 안 맞는다. 배포된 자산을 `pages.dev` 절대
URL 로 직접 받아서 본다. 자세한 것은 [../docs/cloudflare-pages-runbook.md](../../../cloudflare-pages-runbook.md).

## 확장은 여기서 싸인다

`npm run dev` 와 `npm run build` 가 먼저 `scripts/pack-extension.mjs` 를 돌려
`../bridge/` 를 압축한다. 확장 자체를 고칠 때는 [../bridge/CLAUDE.md](../bridge/CLAUDE.md).
