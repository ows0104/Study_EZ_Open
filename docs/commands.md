# 명령 목록 — 무엇을 하려는가에서 명령으로

**이 문서는 목록이다. 왜 그렇게 도는지는 여기 없다** — 설계는
[README](../README.md), 판단 기준은 [CLAUDE.md](../CLAUDE.md), 파이프라인 속은
[docs/pdf2anki.md](pdf2anki.md)에 있다. 여기서는 **하려는 일 → 치는 것**만 적는다.

플래그의 정확한 뜻은 `python -m studyez --help`가 원본이다. 이 표와 어긋나면
`--help`가 맞다.

Python은 PATH에 없다. 아래에서는 앞머리를 줄여 `studyez …`로 적는다.

```bash
PYTHONIOENCODING=utf-8 "$USERPROFILE/anaconda3/python.exe" -m studyez watch
```

`studyez`의 하위 명령은 열하나다 — `match` `watch` `done` `jokbo` `preview`
`agent` `prequeue` `publish` `import` `release` `rebuild`.

---

## 1. 학기 준비 — 과목당 한 번

| 하려는 일 | 명령 | 나오는 것 |
|---|---|---|
| 족보를 강의별로 자른다 | `studyez jokbo 병리학` | `runs/_jokbo/<과목>/` 조각 + `index.json`. 문항·정답·이의제기를 짝짓고 연도별 반복률까지 센다 |
| 족보 PDF를 직접 지정한다 | `pdf2anki.jokbo <족보.pdf> -o out/jokbo` | 위가 부르는 밑단 |
| 올해 강의를 작년 강의에 붙인다 | `studyez match 병리학` · `studyez match --all` | 짝 후보와 「손봐야 할 강의 N편」 보고 |
| 확인한 짝을 굳힌다 | 명령 없음 — `runs/_pairs/<과목>.json`을 사람이 적는다 | 코드는 읽기만 한다. 블럭 경계(`_block`·`_from`·`_until`)도 이 파일이다 |
| 시간표를 서버에 넣는다 | `server/`에서 `app.cli seed-timetable [파일]` | 캘린더가 이것만으로 그려진다. 원본은 `data/timetable/` |

## 2. 복습 덱 (Main-Quiz) — 올해 필기로 만든다

| 하려는 일 | 명령 |
|---|---|
| 무엇을 만들지 보기만 한다 | `studyez watch` |
| 이대로 만든다 | `studyez watch --build` (한 번에 만드는 상한은 `--max`, 기본 2) |
| 한 편만 지목해 만든다 | `studyez watch 기생충학 --run-id 260831_01 --build` |
| 이미 만든 편을 다시 만든다 | 위에 `--force` (`--run-id`가 필요하다) |
| 전략을 정한다 | `--strategy 기본\|필기\|족보\|사진` (기본은 `auto`. 실습 사진 중심이면 `사진`) |
| 밀린 것을 몰아 만든다 | `--all-dates`, 또는 `--since 2026-08-01 --until 2026-08-31` |
| 방금 올라온 파일도 잡는다 | `--now` (동기화가 끝나기를 기다리는 10분을 건너뛴다) |
| 블럭 판정을 확인한다 | `--today 2026-09-10` |
| PDF 하나를 직접 굽는다 | `pdf2anki.run "<올해 필기.pdf>" --strategy … --resume out/<id>` |

`--run-id`로 지목한 편은 **블럭 창·하루 상한·이미 만들었다는 표시를 지난다.**
사람이 그 편을 골랐기 때문이다.

## 3. 예습 덱 (Pre-Quiz) — 예습 대화 + 작년 필기로 만든다

| 하려는 일 | 명령 / 자리 |
|---|---|
| 예습 링크를 저장한다 | 사람이 `/admin`·캘린더에서 저장한다 (`PUT /api/admin/lectures/{과목}/{run_id}/preview`). 대화를 여는 것과 링크를 되가져오는 것은 크롬 확장이 한다 |
| 대화 하나를 손으로 받아 둔다 | `studyez preview 260831_01 --url https://chatgpt.com/share/...` → `runs/<run_id>/preview.md` |
| 자리만 세운다 | `studyez prequeue` (작년 짝 고르기 · `preview.md` 굳히기) |
| 이대로 만든다 | `studyez prequeue --build` |
| 한 편만 | `studyez prequeue 기생충학 --run-id 260831_01 --build` |
| 다시 만든다 | 위에 `--force` |
| 임박한 것만 | `--within-days 3` · 상한 `--max 1` |
| PDF 하나를 직접 굽는다 | `pdf2anki.prequiz.run "<작년 필기.pdf>" --note <링크\|note.md>` |

`prequeue`는 멱등이다 — 링크가 그대로면 건너뛰고(`done`), 링크가 바뀌었는데 덱이
이미 있으면 `stale`로 적어 다시 만든다.

## 4. 덱을 손본다 — 모델을 안 부르는 것들

| 하려는 일 | 명령 |
|---|---|
| 카드는 그대로 두고 덱만 다시 굽는다 | `studyez rebuild` (뒷면 배치·CSS를 고쳤을 때. guid가 안 바뀌어 복습 이력이 산다) |
| 검사 규칙이 늘어 표시를 다시 센다 | `studyez rebuild --reflag` |
| 다른 곳에서 만든 덱을 옮겨 온다 | `studyez import --from "../PDF2ANKI/out"` (옮긴 자리마다 `HOLD`가 붙어 안 나간다) |
| 그 보류를 푼다 | `studyez release 260812_01` |

## 5. 사이트로 올린다 — 강의록·덱·문항·예습 링크

| 하려는 일 | 명령 |
|---|---|
| 한 과목을 올린다 | `studyez publish 기생충학` |
| 아직 안 올라간 것을 전부 훑는다 | `studyez publish --all` |
| 한 편만 올린다 | `studyez publish --run-id 260831_01` |
| 무엇이 올라갈지만 본다 | `--dry-run` |
| 강의록만 먼저 내보낸다 | `--notes-only` |
| 문지기를 끄고 민다 | `--no-gate` (사람이 보고 판단했을 때) |
| 이미 올린 표시를 무시한다 | `--force` |
| 한 편을 마감한다 | `studyez done 260831_01` (표시하고 그 편을 올린다. `--no-publish`면 표시만) |

한 번에 나가는 것 — `notes_current`·`notes_prev`(강의록 PDF) · `main_apkg`·`pre_apkg`와
미디어 · `run-meta` · `main-items`·`pre-items`(웹 풀이용 문항) · 예습 링크.

**`publish`는 올리기 전에 예습 링크를 서버에서 먼저 당겨 온다.** 이 저장소에서
방향이 반대인 것이 그것 하나뿐이라, 안 당기면 방금 바꾼 링크를 옛 주소로
덮어쓴다. `--no-prequeue`로 끈다.

## 6. 러너 — 종일 도는 것

| 하려는 일 | 명령 |
|---|---|
| 러너를 띄운다 | `studyez agent` (과목을 좁히려면 `studyez agent 기생충학`) |
| 붙는지만 본다 | `studyez agent --once` |
| 간격을 바꾼다 | `--poll 15` · `--sweep-minutes 10` · `--no-sweep` |
| 겹쳐 만들 편 수를 바꾼다 | `--workers 2` (기본 2. 서버도 같은 상한을 든다 — 작은 쪽이 실제 상한) |
| 예약 작업으로 등록한다 | `powershell -ExecutionPolicy Bypass -File scripts\install-agent-task.ps1 [-Subject 병리학]` |
| 등록을 뺀다 | 위에 `-Remove` |
| 도는지 본다 | `Get-ScheduledTask -TaskName 'StudyEZ Agent'` |
| 무엇을 하는지 본다 | `runs/agent.log` · 편별 `runs/agent.<run_id>.log` · 쓸기 `runs/agent.sweep.<과목>.log` |
| 얼마나 남았는지 본다 | `/admin` 맨 위(단계·몇 분째·남은 시간) · 캘린더의 그 덱 줄 |

일감은 **재료가 도착하면 저절로 선다**(2026-09-01) — 올해 필기가 처음 올라오면
복습이, 예습 링크가 바뀌면 예습이. 캘린더의 「… 덱 만들기」와 덱 옆의 ⟳는 그
안전장치다(`POST …/prequiz-job?kind=pre|main`, ⟳는 `force`).

자동은 **하루 6편**까지고 넘으면 `held`로 서서 사람을 기다린다. 쓸기(`publish`)는
빌드와 **겹쳐 돈다** — 앞의 편이 막혀도 올릴 것은 올라간다.

## 7. 사이트에서 하는 것 — 여기에 명령이 없는 기능

- **강의록 내려받기** — `GET /api/lectures/{과목}/{run_id}/files/{asset_id}`. 로컬
  명령은 없다. 원본은 Synology에 있고 사이트로는 `publish`가 밀어 올린다
- **웹 풀이(자기채점)** — Pre-Quiz·Main-Quiz의 `reveal`·`grade`, 기록 지우기는
  `DELETE …/attempts`
- **관리자 화면** — 탭 셋으로 갈라져 있다(2026-09-04). 왼쪽부터 `/admin` **퀴즈**는
  위가 도는 일감 판(`/api/admin/prequiz-jobs` — 순서 옮기기·멈추기)이고 아래가
  만들어진 덱 목록(`runMeta`의 문항 수·만든 날·검토 표시), `/admin/users` **계정**은
  승인(대기가 위로 선다), `/admin/lectures` **강의**는 짝 확정(`PUT …/match`) ·
  체크리스트 `waive` · 예습 링크 · 과목 별칭. 러너가 안 붙었는데 일감이 기다리면
  그 경고만 어느 탭에서든 뜬다
- **크롬 확장** — 작년 PDF와 예습 프롬프트를 ChatGPT·Gemini·Claude 새 대화에
  채우고 링크를 회수한다. 스토어용 ZIP은 `chrome-extension\build-store-package.ps1`

## 8. 운영

| 하려는 일 | 명령 |
|---|---|
| API를 배포한다 | `server\deploy.ps1` (손으로. 푸시로는 프론트만 나간다) |
| 표를 세우고 빠진 칼럼을 붙인다 | `server/`에서 `app.cli init-db` |
| 고아 산출물을 지운다 | `app.cli purge-artifacts` → 정말 지우려면 `--apply` |
| 한 학기 지난 작업 폴더를 버린다 | 자동이 없다. `out/`에서 180일 지난 것을 손으로 지운다 |

**`server/app/cli.py`는 `server/.env`를 읽고, 그것은 원격 DB를 가리킨다.** 로컬
사본을 치려면 `DATABASE_URL`을 덮어써라.

## 없는 것

- **야간 크론.** 2026-08-23에 걷어냈다. `scripts/nightly-*.ps1`과
  `scripts/install-scheduled-task.ps1`은 배선만 남아 있고 **등록되어 있지 않다**
- **`runs/` 자동 청소.** 저기에는 다시 만들 수 없는 것이 섞여 있다
- **선택교과·인간사회의료.** 이름을 직접 대도 막힌다
  (`studyez/filenames.py`의 `EXCLUDED_SUBJECTS`·`EXCLUDED_PREFIXES`)
