# 두 앱이 **실제로** 같이 쓰는 것

여기 들어오는 조건은 하나다.

> **Study_EZ 와 땡시(Spotter)가 둘 다 이것을 부른다.**

「나중에 쓸 것 같다」·「비슷하니까 여기 두자」는 안 들어온다. 공유 폴더가 아무것도
거절하지 않으면 웅덩이가 된다 — 저장소가 이미 그 경고를
[docs/refactor-plan.md](../docs/refactor-plan.md) §6 에 적어 두었다.

## 지금 사는 것

    session/    한 번 로그인하면 두 앱이 다 열린다

`session.js` 하나다. `Domain=.studyez.kr` 쿠키에 세션을 담아 형제 서브도메인이
같이 읽는다. **두 앱이 실제로 이 파일을 읽는다** —

    web/src/supabase.ts          import 해서 전역을 세운다 (Vite)
    spotter/web/session.js       사본. `spotter/scripts/sync_shared.py` 가 가져간다

땡시 쪽이 사본인 것은 **거기에 번들러가 없어서**다. 정적 파일을 그대로 내보내고
`<script src="session.js">` 로 부르므로 그 이름의 파일이 실제로 그 자리에 있어야
한다. 사본이 원본과 갈라지면 `sync_shared.py --check` 가 배포 전에 말한다.

## 아직 안 들어온 것 — 그리고 왜

계획(§4)은 여기에 `jokbo/`·`publish/`·`quality/` 도 그렸다. **폴더만 먼저 만들지
않았다.** 셋 다 지금 구현이 **둘**이고, 합치는 것은 파일을 옮기는 일이 아니다.

| | Study_EZ | 땡시 | 합치기 전에 필요한 것 |
|---|---|---|---|
| 족보 파싱 | `quizgen/jokbo.py` 1035줄 | `spotter/scripts/parse_jokbo.py` 365줄 | 같은 열한 쪽에서 둘이 무엇을 내는지 **표로 맞대기** (계획 Phase 3 ①②) |
| R2 올리기 | `runner/publish.py` 720줄 | `upload_web`·`upload_subject` 366줄 | 올릴 키 목록이 글자 하나 안 다른지 (`--dry-run` 비교) |
| 모델로 재기 | `quizgen/reproduce.py` 755줄 | `screen_questions.py` 218줄 | 같은 카드 묶음에 옮기기 전/후 판정이 같은지 |

**빈 폴더를 먼저 만들면 「합쳤다」고 착각하게 된다.** 그 셋 중 하나를 실제로
합치는 날 그때 이 표에서 지운다.
