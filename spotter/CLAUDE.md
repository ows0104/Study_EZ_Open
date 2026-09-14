# spotter — 땡시 (Spotter)

과목 하나 → 사진 문항 세트. **시간 재는 다지선다**이고, Study_EZ 의 자기채점 자유회상과는
다른 제품이다 — 한쪽을 고칠 때 다른 쪽을 볼 일이 없다.

    무엇을 고치면 어느 파일인가    ../docs/map.md §2
    검사                          pytest tests/spotter     22개 · 7초
    배포                          ../docs/layout.md §4     두 걸음이다
    권한 · 어디서나 미는 함정       ../CLAUDE.md

**`quizgen`·`runner` 를 import 하지 않는다.** 서버와만 HTTP 로 만난다(`/api/spotter/…`
경로 10개). 그래서 이쪽을 고칠 때 Study_EZ 파이프라인을 읽을 일이 없다.

## 손으로 고치는 파일은 여섯이다

`data/` 에 24개가 있는데 **대부분은 만들어지는 것**이다. 고칠 것은 이것들이다.

    question_corrections.json   족보 정답표가 틀렸을 때
    image_overrides.json        사진에 이름표가 잘못 붙었을 때
    species.csv                 종 마스터 (학명·감염경로·증상·치료…)
    specimens.csv               표본 마스터 (충란·성충·염색·배율…)
    glossary.json               용어 별칭
    identification_pairs.csv    사진으로 구별이 불가능한 짝

나머지(`generated_exams.json`·`coverage.csv`·`images.json`·`past_questions*.json`…)는
스크립트가 만든다. **거기를 고치면 다음 빌드에 덮인다.**

고친 뒤 도는 순서:

```bash
python spotter/scripts/build_master.py     # species.csv·specimens.csv → .json
python spotter/scripts/build_web.py        # → build/quiz_db.json
python spotter/scripts/upload_web.py       # → R2
```

## 화면은 둘이고 하나는 판이 하나다

    web/                     기생충학 화면
    web/anatomy/             해부학 넷. `_template.html` 한 판 + 설정이다

**해부학은 2026-09-14 까지 사본 셋이었고 그 사이에 실서비스 버그가 끼어 있었다** —
`trunk`·`head-neck` 이 사진이 없는 상대경로를 부르고 있었다. **사본이 셋이 아니었으면
못 생길 종류다.** 1,950줄을 판 696 + 설정으로 합쳤고 `build_anatomy.py --check` 가
판과 산출물이 같은지 본다.

## 사본이 하나 남아 있다 — `web/session.js`

원본은 `../platform/session/session.js` 다. **여기서 고치면 다음 동기화에 덮인다.**
사본이 남은 이유는 이 앱에 빌드 도구가 없어서다(`scripts/sync_shared.py` 머리에 적혀 있다).
갈라졌는지는 그 스크립트가 본다.

```bash
python spotter/scripts/sync_shared.py --check
```

## `spotter-dist/` 는 산출물이다

**손으로 고치지 마라.** `spotter/` 를 고치고 `scripts/deploy_pages.py` 를 돌리면 거기로
옮겨지고 `<script src>` 마다 내용 해시가 붙는다. **거기까지는 아직 배포가 아니다** —
밖으로 나가는 둘째 걸음과 `--force` 가 필요한 이유는 [../docs/layout.md](../docs/layout.md) §4 에 있다.
