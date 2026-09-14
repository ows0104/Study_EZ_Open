# 어느 폴더가 무엇인가

> 고칠 것이 정해져 있다면 [map.md](map.md) 가 더 빠르다 — 일감별로 읽을
> 경로와 연결부를 적어 두었다. 이 문서는 **왜 지금 모양인가**를 적는다.

2026-09-14 에 저장소 셋을 하나로 합치고 폴더 이름을 하는 일로 바꿨다. **옛
이름으로 적힌 문서·커밋·로그가 많다.** 그것들을 고치지 않은 이유는 아래 §3 에 있다.

## 1. 지금 모양

```
Study_EZ_Open/
  server/        서버          FastAPI · Cloud Run. 두 앱이 만나는 유일한 자리
  web/           프론트        Vite + React. studyez.kr
  quizgen/       퀴즈생성      강의록 PDF → 복습·예습 카드 (모델이 쓴다)
    prequiz/                   예습만의 계약. 거울이 아니라 `..build`·`..pack` 을 부른다
    prompts/                   빈 세션이 그대로 읽는 지시
  runner/        연결부        이 노트북에서 파이프라인을 돌리고 서버로 민다
  spotter/       땡시 소스     과목 하나 → 땡시 문항 세트
    scripts/                   재료 모으기 · 문항 조합 · 배포
    web/                       기생충학 화면 + `anatomy/` 해부학 넷
  spotter-dist/  땡시 배포본   Pages 가 내는 것과 같은 모양. **손으로 고치지 마라**
  bridge/        예습링크      크롬 확장. 작년 필기를 AI 새 대화에 채우고 링크를 회수
  platform/      공유          두 앱이 **실제로** 같이 쓰는 것만 (`platform/README.md`)
  tests/         검사          `pytest tests` (개수는 map.md 가 든다)
  scripts/       운영          예약 작업이 부르는 ps1 + 손도구 셋
  docs/          문서          `archive/` 는 닫힌 기록. 현재 상태로 읽지 마라
  runs/  out/    산출물        추적 안 됨. 23GB
```

**`server/` 와 `web/` 은 자리를 안 옮겼다.** 저장소 밖 설정이 이 경로를 알고 있다 —
Cloudflare Pages 대시보드가 `web/` 을, `server/Dockerfile` 과 `deploy.ps1` 이
`server/` 를 본다. 옮기면 저장소만으로는 못 고치는 것이 같이 깨진다.

## 2. 무엇이 무엇으로 바뀌었나

| 옛 이름 | 지금 | 왜 |
|---|---|---|
| `pdf2anki/` | `quizgen/` | 산출물 형식(Anki)이 이름이라 하는 일이 안 보였다 |
| `studyez/` | `runner/` | 제품 이름과 같아서, 이 폴더만 가리키는 말이 없었다 |
| `studyez/runner.py` | `runner/cycle.py` | `runner.runner` 가 된다. 내용은 「야간 러너 한 사이클」이다 |
| `chrome-extension/` | `bridge/` | 어느 확장인지가 아니라 무엇으로 만들었는지를 말하고 있었다 |
| `packages/session/` | `platform/session/` | 공유물이 들어가는 자리를 하나로 |
| `ows0104/Spotter_Quiz_source` | `spotter/` | 이력째 들어왔다(subtree) |
| `ows0104/Spotter_Quiz` | `spotter-dist/` | 얕은 사본이라 경계를 뿌리로 접붙여 13커밋을 살렸다 |

명령도 같이 바뀐다.

    python -m studyez watch     →  python -m runner watch
    python -m pdf2anki.run      →  python -m quizgen.run

## 3. 옛 이름을 남겨 둔 자리

**과거를 말하는 문장은 안 바꿨다.** 그때 실제로 그 이름이었고, 커밋 메시지와
로그가 그 이름으로 적혀 있다. 문서를 고쳐 놓으면 `git log` 를 볼 때 짝이 안 맞는다.

**예외가 하나 있다 — [refactor-plan.md](refactor-plan.md) 의 본문은 이름만 고쳤다.**
그 문서는 「어디를 고칠 계획인가」라서, 지금 트리에 없는 경로를 가리키면 못 쓴다.
숫자는 09-12 실측 그대로 두고 이름만 옮겼다는 것을 그 문서 §0 머리에 적어 두었다.

- `docs/interview.md` — 관리자 인터뷰 전사
- `docs/archive/` — 스스로 「닫았다」고 적은 인계 메모 넷
- 「파이프라인이 pdf2anki로 갈리면서…」 같은 문장 — 지금 이름을 괄호로 덧붙이기만 했다
- `runs/*/run.meta.json` 의 `"pipeline": "pdf2anki"` — 옛 덱 72편. 읽는 쪽이 없다

## 4. 배포는 여전히 셋이다

소스는 하나, 배포는 셋. 합치지 않는 이유는 [docs/sibling-apps.md](sibling-apps.md)
에 있다 — **하나가 깨져도 나머지가 산다.**

    studyez.kr            Cloudflare Pages  ← web/            (push 하면 저절로)
    spotter.studyez.kr    Cloudflare Pages  ← spotter-dist/   (아래)
    studyez-api           Cloud Run         ← server/         (`server/deploy.ps1` 손으로)

### 땡시를 배포하는 법

두 걸음이다. **첫 걸음은 이 저장소 안에서 끝난다.**

    python spotter/scripts/deploy_pages.py spotter-dist      원본 → 배포본
    python spotter/scripts/deploy_pages.py --check spotter-dist   고치지 않고 보기만

`deploy_pages.py` 가 공용 스크립트 넷·기생충학 화면·해부학 넷을 `spotter-dist/` 로
옮기고 `<script src>` 마다 내용 해시를 붙인다. 여기까지는 배포가 아니다.

**둘째 걸음이 밖으로 나간다.** Cloudflare Pages 가 `ows0104/Spotter_Quiz` 를
지켜보다가 push 하면 그 루트를 그대로 낸다. 그래서 `spotter-dist/` 를 거기로 민다.

> **그 저장소의 `.github/workflows/pages.yml` 은 배포하는 것이 아니다.** GitHub
> Pages 로 내려는 옛 워크플로인데 그 저장소에 Pages 가 안 켜져 있어서
> `HttpError: Not Found` 로 **push 마다 실패한다**(2026-09-07 부터 확인됨).
> 실제 배포는 Cloudflare 가 하므로 사이트는 멀쩡하다 — 다만 push 할 때마다
> 빨간 X 가 뜨니 그것을 배포 실패로 읽지 마라.

    git subtree push --prefix=spotter-dist https://github.com/ows0104/Spotter_Quiz.git main

**지금은 이 명령이 그대로 안 통한다.** 들여올 때 그 저장소의 사본이 얕아서
(shallow) 경계를 뿌리로 접붙여 이력을 되살렸고, 그 과정에서 커밋 해시가 바뀌었다.
내용은 같지만 원격과 계보가 갈린 상태라 `--force` 가 필요하다.

    git subtree split --prefix=spotter-dist -b _dist
    git push --force https://github.com/ows0104/Spotter_Quiz.git _dist:main
    git branch -D _dist

**산출물 저장소라 이력을 다시 써도 잃는 것이 없다** — 내용은 여기서 다시 만들어진다.
다만 되돌릴 수 없으므로 **사람이 정한다.** 한 번 밀고 나면 그 뒤로는 `subtree push`
가 그냥 통한다.

대시보드에서 바꿀 것은 **없다.** Pages 설정은 그 저장소 안의
`.github/workflows/pages.yml` 이 전부이고 그것도 같이 들어와 있다.
