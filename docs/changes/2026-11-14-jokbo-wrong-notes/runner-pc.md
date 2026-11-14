# 러너 컴퓨터에서 할 일 (2026-11-14)

운영 자격 정보(`server/.env`의 운영 `DATABASE_URL`·`RUNNER_TOKEN`)가 있는 러너 컴퓨터에서 한다.
두 가지이고 서로 독립이다. 비밀값은 화면·채팅·커밋에 남기지 않는다.

## 1. 족보 오답노트 표 만들기 (PR #160 병합 전에)

PR #160 코드가 필요하다(표 정의 `server/app/models/jokbo.py`). master는 건드리지 않고 별도 worktree에서 한다.

```powershell
cd <Study_EZ_Open 저장소>
git fetch origin
git worktree add ..\Study_EZ_jokbo-table origin/claude/jokbo-wrong-notes
cd ..\Study_EZ_jokbo-table\server
<저장소>\server\.venv\Scripts\python.exe ..\docs\changes\2026-11-14-jokbo-wrong-notes\create_table.py <저장소>\server\.env
```

- 성공: `jokbo_mark: 새로 만듦 · RLS 켜짐` (다시 돌리면 `이미 있음(그대로 둠)`).
- `postgres가 아닙니다`가 나오면 운영 .env가 아니다 — 아무것도 바꾸지 않고 멈춘 것이다.
- 이 표 하나만 만든다. 기존 표·데이터는 읽지도 바꾸지도 않는다.
- 끝나면 `git worktree remove ..\Study_EZ_jokbo-table`. 그다음 PR #160 병합 → API·웹 자동 배포.

## 2. 족보를 학생에게 공개 (운영 R2에 올리기, DB 변경 없음)

족보 풀이 자료(`2026-1/` 폴더, 약 18MB)는 **git에 없다** — 저장소가 공개라 족보 원문·그림·해설을 올리지 않는다.
작업 컴퓨터에서 `runs/_materials/감염과 면역/jokbo-solve/2026-1/` 폴더를 비공개 경로로 받아 둔다
(예: 받은 위치 `D:\jokbo-solve\2026-1`). 코드는 master에 있다(#150).

```powershell
cd <Study_EZ_Open 저장소>
git pull
.\server\.venv\Scripts\python.exe -m runner.jokbo_solve upload --audience all --root D:\jokbo-solve
```

- `--root`는 `2026-1`을 **담은** 폴더다. 러너 토큰은 `server/.env`의 `RUNNER_TOKEN`을 스스로 읽는다.
- 그림 155개 중 없는 것만 먼저 보내고, 49칸 문서를 `audience: all`로 올린다. 끝에 칸마다 `"audience": "all"`이 찍힌다.
- 다시 돌려도 같은 내용으로 덮을 뿐이다. 되돌리기는 같은 명령에 `--audience admin`.
- 1번과 순서 무관.
