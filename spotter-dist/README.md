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

## `update_exam_trends.py` 만 여기 산다

해부학 문항의 표집 가중치를 기출빈도 워크북에서 다시 계산하는 도구다.
**원본이 여기밖에 없다** — 해부학 `index.html` 넷이 그랬던 것과 같은 모양이고
(2026-09-14 에 그쪽은 `spotter/web/anatomy/` 로 회수했다), 이것은 아직 안 옮겼다.
옮길 때는 이 줄을 지워라.

가중치는 `sqrt(n + 1)` 이다(`n` 은 기출 횟수). 영역 편중은 따로 막는다 — 한 영역이
균등 기준보다 한 문제 넘게 나오지 않고, 이어지는 문항은 가능하면 다른 영역에서
고른다. 같은 구조물은 한 판에 한 번만 나온다.

    python update_exam_trends.py "C:\path\to\인체해부학_차시별_구조물_기출빈도.xlsx"
