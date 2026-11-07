# 배포와 그 뒤의 측정 — 2026-11-07~08

## 배포 경로

PR #21은 `4f48b2a5`로 master에 병합됐고 `Tests and build`는 통과했다. 그 SHA의 배포 작업은
거부됐다 — 검사가 도는 사이 다른 세션이 PR #23(16:36:56Z)과 PR #22(16:37:18Z)를 병합해
master가 전진했고, `scripts/ci_deploy.py:73`의 `assert_head`가 막았다:

```
ValueError: This run was superseded by a newer master commit; refusing deployment
```

설계된 안전장치이며 이 변경의 결함이 아니다. PR #23의 배포도 같은 이유로 거부됐다.
반영된 것은 **`cc67288b`**(PR #22) 실행이고, 그 커밋에 이 변경이 들어 있다.

## 반영 확인 (읽기 전용)

| 확인 | 결과 |
|---|---|
| `GET /api/health` | `{"status":"ok","environment":"production","revision":"cc67288bab3343936d0ac0a797d58546b1c423de"}` |
| 무인증 보호 경로 | `GET /api/timetable` 401 · `GET /api/spotter/db` 401 |
| 트래픽 | `studyez-api-release-423922158951` 100% |
| 그 revision의 런타임 | `containerConcurrency` **8** · cpu 1 · 512Mi |
| master의 `latest()` | `.limit(1)` 들어가 있음 |
| 배포된 웹 청크 | `RootGenerationPanel-DlXaZ1mO.js` — `setInterval` 0회, `setTimeout` 4회 / `clearTimeout` 3회 |

동시성 8은 병합 전에 `gcloud run services update --concurrency 8 --no-traffic`으로 서비스 틀에만
넣었고(트래픽은 옛 revision에 그대로 두었다), 자동 배포의 새 revision이 그것을 물려받았다.
`ci_deploy.py`가 런타임 설정 플래그를 넘기지 않고 트래픽을 revision 이름으로 고정하기 때문에
이 순서가 필요했다.

## 예측은 맞지 않았다

`baseline.md`에서 적은 확인 조건은 "261104_02의 `GET …/generation`이 다른 강의와 같은
수십 밀리초대로 내려오는가"였다. **내려오지 않았다.**

새 revision이 처리한 유일한 실제 사용자 구간(16:52:0x, 인스턴스는 70초 전에 생김):

| 요청 | 지연 | 수정 전 |
|---|---|---|
| `admin/root-learning/…/261104_02/generation` | **2.323s** | median 2.736s · max 6.328s |
| `main-quiz/lectures/…/261104_02/entry` | 1.320s | 7.196s |
| `admin/root-learning/…/261104_02` | 1.437s | — |
| `root-learning/lectures/…/261104_02` | 0.662s | — |
| **`me`** | **0.961s** | 따뜻할 때 0.033s |
| `notices` | 0.069s | — |

표본은 이 한 구간뿐이고, 다섯 요청이 한 인스턴스에서 2초 안에 겹쳤다. **`/api/me`가 0.961초**인 것이
중요하다 — 그 엔드포인트는 따뜻할 때 0.033초다. 즉 그 구간에는 핸들러와 무관하게 전부 느렸다.
그래서 2.323초 중 얼마가 `latest()`의 몫인지 이 한 표본으로는 가를 수 없다.
개선됐다고도, 효과가 없었다고도 적지 않는다.

## 격리 측정이 배제한 것

`.limit(1)`이 든 상태로 격리 SQLite에서 쟀다(가장 최근 판이 큰 `result`를 싣는 경우):

| 판 수 | `result` JSON | 엔드포인트 |
|---|---|---|
| 2 | 275,925 B | 0.0107s |
| 2 | 1,125,451 B | 0.0211s |
| 2 | 2,531,951 B | 0.0446s |

2.5 MB를 실어도 0.045초다. **판 수도, `result` 크기도 로컬에서는 초 단위를 만들지 못한다.**
운영과의 차이는 DB 전송이다 — Supabase Postgres를 transaction pooler로 쓴다. 남은 설명은
그 큰 `result` JSONB를 Cloud Run까지 끌어오는 비용이고, `.limit(1)`은 **여러 판**만 줄였을 뿐
가장 최근 한 판의 `result`는 그대로 끌어온다.

## 다음 수 (아직 하지 않았다)

폴링 경로에서 `result` 열을 아예 적재하지 않는 것(`defer`/`load_only`), 또는 폴링 전용
경량 응답. `plan.md`에서 "먼저 `.limit(1)`의 효과를 재고 판단한다"며 미뤄 둔 것이고,
위 측정이 그쪽을 가리킨다. 사람 승인을 받고 별도 작업으로 한다.

곁: 이번에도 두 번 인코딩된 subject 요청이 있다. 별건이다.
