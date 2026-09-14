# 땡시 배포본 — **손으로 고치지 마라**

여기 있는 것은 전부 `spotter/` 에서 만들어진다. 고칠 것은 원본이고, 여기 고친 것은
다음 배포에 덮인다.

    python spotter/scripts/deploy_pages.py spotter-dist            원본 → 여기
    python spotter/scripts/deploy_pages.py --check spotter-dist    고치지 않고 보기만

절차 전체는 [docs/layout.md](../docs/layout.md) 에 있다.

## 내는 것은 Cloudflare 다

`ows0104/Spotter_Quiz` 로 push 하면 Cloudflare Pages 가 이 루트를 그대로 낸다
(`spotter.studyez.kr`). **GitHub Pages 가 아니다** — 그렇게 내려던 워크플로가
2026-09-14 까지 있었는데, 그 저장소에 Pages 가 안 켜져 있어서 push 마다
`HttpError: Not Found` 로 실패하고 있었다. 빨간 X 가 배포 실패로 읽혀서 지웠다.

`_headers` 의 `Cache-Control: no-store` 가 여기 있는 것 전부에 걸린다. 화면은
껍데기뿐이고(다 합쳐 100KB 남짓) 문항과 사진은 서명 URL 로 따로 오므로 캐시해서
아낄 것이 거의 없다. 반대로 캐시가 남으면 고친 로그인 문이 네 시간 늦게 나간다.

## 들어 있는 것

    index.html              과목 고르는 화면
    parasitology/           기생충학 (사지선다)
    exam1/ trunk/           해부학 — 판 하나에서 찍는다
    head-neck/ neuro/       (`spotter/web/anatomy/`)
    config.js               **배포본이 사실이다.** deploy 가 안 덮는다
    session.js auth.js gate.js   공용. 다섯 과목이 같이 쓴다
    _headers                Cloudflare 응답 헤더

## 소스 파일은 여기 두지 마라

**이 폴더는 공개로 서빙된다.** 2026-09-14까지 `update_exam_trends.py` 가 루트에
있어서 `spotter.studyez.kr/update_exam_trends.py` 로 누구나 받아 갈 수 있었다.
그날 `spotter/scripts/` 로 회수했다.

문항 DB 도 같은 이유로 2026-09-06 에 걷어 냈다. 지금은 R2 에 있고 로그인한
사람에게만 서명 URL 로 간다.
