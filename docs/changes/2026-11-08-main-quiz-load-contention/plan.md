# 구현 계획 — Main-Quiz 로딩 지연 재발

브랜치 `claude/main-quiz-load-contention` (origin/master `e73ccf0a` 위).
대시보드 claim `3376dfd4`. 겹치는 행 없음(free-notes는 `web/src/notes`·`server/app/.../notes`,
redesign-1107-feedback는 `web/src/calendar`·`calendar.css`·`GuidePage.tsx`와 캘린더 4개 테스트,
Map 세 세션은 `content/prompts`·`docs/changes`·`runs`).

## 1. 관리자 generation 질의를 한 판으로 제한한다

`server/app/routes/root_generation.py` `latest()`에 `.limit(1)`을 붙인다.
`order_by(created_at.desc())`는 그대로 두고 응답 필드는 건드리지 않는다.
`root_learning.py:235`의 질의는 판을 **훑어야** 하므로 바꾸지 않는다.

## 2. 폴링을 응답 뒤에 예약한다

`web/src/bank/RootGenerationPanel.tsx`의 `setInterval(…, 3000)`을, 응답이 돌아온(또는 실패한)
뒤 3초를 세는 자기 예약 `setTimeout` 사슬로 바꾼다. 효과는 간격 >= 응답 시간이 되어
겹친 요청이 쌓이지 않는 것이다. `pending` 판정·`setJob`·`onPublished` 호출·오류 표시·
unmount 정리는 그대로 둔다. 진행이 끝나면(`pending`이 거짓) 사슬을 멈춘다.

## 3. Cloud Run 동시성을 명시한다

`server/deploy.ps1`에 `--concurrency 8`을 추가한다(현재 기본 80). 코어 하나·프로세스 하나에
80개를 쌓지 않고 포화 전에 인스턴스를 늘리게 한다. 자동 배포(`scripts/ci_deploy.py`)는
`--concurrency`를 넘기지 않고 런타임 설정을 보존하므로, 운영에는 설정만 한 번 바꾼다:

```powershell
gcloud run services update studyez-api --project meddeck-503318 --region asia-northeast3 --concurrency 8
```

이것은 이미지와 코드를 바꾸지 않는 설정 전용 새 revision이다. **사용자 승인 뒤에 실행한다.**
`--min-instances`·CPU·메모리·`--max-instances`는 이번에 바꾸지 않는다.

## 4. 검사

| 검사 | 명령 | 확인하는 것 |
|---|---|---|
| 새 서버 검사 | `-m pytest tests/test_root_generation_poll.py -q` | 여러 판이 있어도 한 행만 적재, 응답 필드 보존 |
| 기존 root 서버 검사 | `-m pytest tests/test_root_generation.py tests/test_root_web_generation.py tests/test_root_one_click.py tests/test_root_parallel_generation.py -q` | 중복·재개·판 승계 동작 유지 |
| 경로 계약 | `-m pytest tests/test_route_contract.py -q` | 관리자 경로·응답 계약 유지 |
| 새 웹 검사 | `web/tests/root-generation-poll.tsx` | 응답 전에는 다음 폴링을 보내지 않는다 |
| 웹 타입·빌드 | `npm run build` | 기존 화면 유지 |
| 배포 실패 경로 | `-m pytest tests/test_deploy_script.py -q` (있으면) | deploy.ps1 인자 변경이 기존 검사와 맞는지 |

## 5. 배포와 확인

master 병합은 자동 배포(API + Pages)다. 사용자 승인 뒤에만 병합한다.
배포 후 `docs/changes/2026-11-08-main-quiz-load-contention/deployment.md`에
운영 로그의 같은 엔드포인트 지연을 **수정 전/후로 나란히** 적는다. 측정하지 못했던
`latest()` LIMIT의 몫은 그때 확인한다. 개선이 확인되지 않으면 성공으로 적지 않는다.
