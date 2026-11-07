# 관측과 요구 — Main-Quiz 로딩 지연 재발

## 관측 (운영 Cloud Logging, studyez-api, 2026-11-07)

### 사용자가 느낀 지연은 새 인스턴스의 콜드스타트다

11:58:20.221에 **서로 다른 네 인스턴스**가 각자의 첫 요청을 같은 순간에 끝냈다.

| 지연 | 요청 | 인스턴스(앞 16자) |
|---|---|---|
| 7.196s | `GET /api/main-quiz/lectures/감염과 면역/261104_02/entry` | `00e8a408bdec7f50` |
| 6.305s | `POST /api/timetable/study-progress` | `00e8a408bde54672` |
| 3.554s | `GET /api/admin/preview-prompt` | `00e8a408bdab3f69` |
| 2.708s | `GET /api/admin/root-learning/.../generation` | `00e8a408bdba656f` |

`00e8a408bdec7f50`의 **가장 이른 로그 줄이 11:58:20.221348**이다. 그 인스턴스는 그 요청
직전에 생겼다. 3초 뒤 11:58:23–27에 같은 인스턴스들이 같은 종류의 요청을 0.03–0.50초에
처리했다. 즉 핸들러가 느린 것이 아니라 **컨테이너 기동이 요청 시간에 들어갔다.**

### 그 스케일아웃을 부른 부하는 관리자 폴링이다

`00e8a408bda2b426`의 가장 이른 로그 줄은 11:51:53.58이므로 11:58:06에는 6분째 **따뜻한**
인스턴스였다. 그 따뜻한 인스턴스에서 `GET /api/admin/root-learning/lectures/감염과 면역/261104_02/generation`이
11:58:06 4.686s · 11:58:09 2.736s · 11:58:16 2.840s였다. 14:27–14:43 구간에서도 세 인스턴스에서
2.040 · 2.140 · 2.914 · 3.478 · 4.215 · 4.450 · 4.586 · 6.328초였다.

화면은 이것을 **3초 고정 간격**으로 호출한다(`web/src/bank/RootGenerationPanel.tsx` `setInterval(…, 3000)`).
간격이 응답 시간보다 짧으므로 응답을 기다리는 요청이 계속 겹쳐 쌓인다.

### 쌓여도 인스턴스가 늦게 늘어난다

`server/deploy.ps1`은 `--cpu 1 --memory 512Mi --min-instances 0 --max-instances 4`로 배포하고
`--concurrency`를 주지 않아 **기본값 80**이다. 컨테이너는 `uvicorn --workers 1`(`server/Dockerfile`)
단일 프로세스다. 코어 하나가 동시 80개를 받을 때까지 Cloud Run은 인스턴스를 늘릴 이유를 못 찾으므로,
먼저 전체가 느려지고 뒤늦게 늘릴 때 그 콜드스타트가 사용자 요청에 얹힌다.
keepalive 핑(Cloud Scheduler `studyez-api-keepalive`, 5분)은 인스턴스 **하나**만 깨워 둔다 —
확인 결과 ENABLED이고, 따뜻한 인스턴스의 `OPTIONS /api/me`는 0.208–0.221초다.

### 핸들러 쪽의 확인된 결함

`server/app/routes/root_generation.py`의 `latest()`는

```python
db.scalars(select(RootGeneration).where(RootGeneration.subject == subject, RootGeneration.run_id == run_id)
           .order_by(RootGeneration.created_at.desc())).first()
```

로 **LIMIT 없이** 질의한다. `RootGeneration`은 `packet`·`result`·`web_dispatch`·`web_response`
네 개의 JSON 열을 한 표에 두므로, 그 강의의 모든 판이 결과 집합에 들어간다. 첫 행만 쓰고 나머지는 버린다.
운영 DB는 Supabase Postgres를 Transaction pooler로 쓴다(`docs/deployment.md`).

### 지난번 수정은 살아 있다 (격리 SQLite, 108문항 × 2강의)

| 요청 | 2026-11-07 측정 | 2026-10-19 기록 |
|---|---|---|
| `GET …/bank` | 0.044s / 9쿼리 | — |
| `POST /api/bank/batch/next` | 0.081s / 21쿼리 | — |
| `POST …/prepare-buffer` near | 0.144s / 11쿼리 / 31,063 B | 0.117s / 11쿼리 / 31,063 B |
| `POST …/prepare-buffer` full | 1.365s / 11쿼리 / 296,760 B | 1.252s / 11쿼리 / 173,799 B |

쿼리 수와 near 응답 바이트가 당시 기록과 같다. 따뜻한 운영 인스턴스에서도 10:47 약리학 세션의
`GET …/bank` 0.385s, `POST …/next` 0.409s였다.

## 측정하지 못한 것

- `latest()`의 LIMIT 누락이 따뜻한 인스턴스의 2.0–6.3초 중 **얼마**를 차지하는지는 측정하지 못했다.
  격리 SQLite는 결과 집합을 스트리밍하므로 6판 × 276 KB 적재에서도 0.0117초이고, 운영의
  Postgres 경로를 재현하지 못한다. 수정 뒤 운영 로그의 같은 엔드포인트 지연으로 확인한다.
- 운영 DB의 강의별 generation 판 수와 `result` 실제 크기는 읽지 않았다.
- 12:07:57 `GET /api/lectures/%25EA%25B0%2590…/261104_02/bank` 404는 subject가 두 번
  인코딩된 별건이다. 이번 범위가 아니다.

## 요구

1. `latest()`는 가장 최근 한 판만 적재한다. 응답 필드는 그대로 유지한다.
2. 관리자 화면의 폴링은 **앞 요청이 끝난 뒤에** 다음 요청을 예약한다. 겹친 요청이 쌓이지 않는다.
   진행 중 표시·완료 감지·게시 콜백은 그대로 동작한다.
3. Cloud Run은 CPU가 포화되기 전에 인스턴스를 늘린다. 수동 배포 경로에 동시성을 명시한다.
   자동 배포(`scripts/ci_deploy.py`)는 런타임 설정을 보존하므로 설정을 한 번 바꾸면 유지된다.
4. 출제·은행·문항·학습 기록·DB 스키마·관리자 응답 계약을 바꾸지 않는다.
