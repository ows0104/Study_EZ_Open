# Study_EZ 서버

FastAPI API다. 인증·자료 배급·학습 기록·관리 기능·생성 작업 큐를 담당한다.
실제 생성은 로컬 러너가 수행한다. 수정 위치와 계약은 [CLAUDE.md](CLAUDE.md)에 있다.

## 로컬 실행 (PowerShell)

`server/` 폴더에서 실행한다. 기존 `.env`가 운영 DB를 가리킬 수 있으므로
로컬 DB를 환경 변수로 먼저 지정한다.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
$env:ENVIRONMENT = "local-test"
$env:DATABASE_URL = "sqlite:///./local_test.db"
$env:RUNNER_TOKEN = "local-runner-token"
.venv/Scripts/python.exe -m app.cli init-db
.venv/Scripts/python.exe -m app.cli seed-timetable
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

`local-test`는 파일을 로컬 디스크에 저장하고 `local-test-token`으로 인증한다.
이 모드는 로컬 확인용이다. 웹 연결은 [웹 README](../web/README.md)를 따른다.

## 검사

```powershell
.venv/Scripts/python.exe -m tests
.venv/Scripts/python.exe -m tests bank
.venv/Scripts/python.exe -m tests.test_route_contract
```

검사는 자체 로컬 DB를 사용하며 파일별 새 프로세스에서 돈다.
`pytest server/tests`는 지원하지 않는다. 검사 파일 목록은 `tests/test_*.py`가 기준이다.

## Quiz Bank 학습도와 망각

현재 숙련도는 마지막 회상 평가 지수에 `R(t,S) = 1 / (1 + t/(9S))`를 곱한다.
`t`는 마지막 평가 이후 일수, `S`는 개념 × 회상 방향별 기억 유지 기간(일)이다.
S일 뒤 지수의 90%가 남는 [FSRS v4 곡선 형태](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm/d040f23afdfcc33a1fab734f821008668ccfd116)를 참고했다.
FSRS 전체 구현이나 개인 데이터로 보정한 정답 확률은 아니며, 안정성 갱신은 자체 휴리스틱이다.

- `policy.json`의 `forgetting`이 수치의 원본이다. 초기 S는 Again 0.25일, Hard 0.5일, Good 1일, Easy 2일.
- 4시간 미만 반복에서는 S가 늘지 않는다. 그 이후 성공 시 `S × (1 + (growth - 1) × min(1, t/S))`로 늘어난다.
  growth는 Hard 1.1, Good 2, Easy 3이다. Again은 S를 절반으로 줄이되 최대 1일로, 전체 범위는 0.25~365일로 제한한다.
- 성공 회상은 이전에 쌓은 평가 지수를 회복한 뒤 EMA로 갱신한다. Hard·Again은 현재 감쇠한 지수에서 갱신한다.
  복습 간격은 기존 일정과 S일 중 짧은 쪽을 사용한다.
- 강의 점수는 감쇠한 숙련도를 목표와 비교한 개념별 비율 `p`로 `100 × (1 - sqrt(mean((1-p)²)))`를 계산한다.
  부족한 개념이 더 크게 반영되며, 출제·개념 지도·강의 상세·캘린더가 같은 추정을 쓴다.
- 조회 시 계산하므로 DB 감산 작업은 없다. 기존 기록의 S는 1일로 가정하며, 학습 시각도 없는 기록은 다음 평가 전까지 감쇠하지 않는다.
  새 필드는 기존 상태 JSON에 저장해 DB 칼럼 추가가 필요 없다. 완료한 회차의 결과는 당시 값으로 보존한다.

## 강의별 오늘 학습 완료

`study_engine/daily_queue.py`가 문항별 오늘 할 일을 계산한다. 모든 새 카드와 한국 날짜 기준
예정된 복습이 대상이며, 변형·심화 문항도 각각 센다. 새 카드를 복습보다 먼저 제시한다.
일반 풀기와 모아풀기는 같은 순서 정책을 쓴다. 처음에는 미평가 선행문항을 먼저 풀고 강의자료(S1)의
슬라이드 순서를 따른다. 같은 슬라이드에서는 회상 단계, 페이지 정보가 없으면 원래 문항 순서를 쓴다.
같은 개념의 다른 회상방향 사이에는 다른 문제 4개를 목표로 3~5개를 두며, 후보가 부족하면 간격을 완화한다.
복습은 원래 예정일의 지연 일수와 현재 약점·중요도·시험 가중치를 반영해 무작위로 고른다.
오늘 예정된 복습은 당일 시각까지 기다리지 않는다. 이미 평가한 선행문항은 복습마다 다시 요구하지 않는다.
각 문항을 평가하면 등급에 관계없이 오늘 완료다. Again·Hard의 다음 복습은 다음날부터다.
평가 이력에 `next_due_at`을 기록하며, 옛 기록은 기존 문항 일정으로 이어간다. DB 칼럼 추가는 없다.

`lectureGoal`은 total/completed/remaining과 처음 학습·복습·재학습 잔여 수를 반환한다.
새 카드와 예정된 복습의 남은 수가 0일 때 완료한다. 임의 종료와 선택한 문항 수 상한은 완료와 별개다.
`firstPassSeen/firstPassTotal`은 각 문항을 한 번이라도 평가한 범위이며 성공 회상 비율은 아니다.
숙련도·시험 목표는 일일 완료를 대신하지 않으며, 시험 미연결 강의도 같은 완료 규칙을 쓴다.

`POST /api/bank/batch/next`는 선택한 강의 전체에서 후보를 고른다. 새 카드가 남으면 신규 풀에서 고르고,
이후 복습 풀에서 고른다. 신규는 선택한 강의 순서와 강의별 슬라이드 흐름을 기본으로 하되 회상방향 간격을
확보할 때 다른 강의로 넘어갈 수 있다. 간격은 선택한 강의 전체의 오늘 풀이 이력으로 센다.
개념 ID가 같아도 다른 강의의 개념은 구분한다. `batchGoal`은 선택한 강의 전체의 새 카드·복습 완료다. 기록은 기존
강의별 `BankState`에 저장하며 되돌리기도 마지막 평가의 실제 강의에 적용한다.
기억 확인형 객관식은 `/bank/options`에서 선지를 먼저 공개하고 `/bank/reveal`에서 답을 공개한다.
선지 공개 상태는 문항 토큰과 함께 저장하며 정답 열람·평가와 구분한다.

## 시험별 하루 목표

`GET /api/study-plan?target=90`은 승인된 사용자의 목표를 계산한다. 목표는 50~100, 기본 90이다.
같은 과목명의 다음 필기시험에 강의를 연결하며, 범위를 알 수 없는 시험은 미연결로 표시한다.
실습·다른 과목·이전 시험 범위는 포함하지 않는다.

전체 학습률은 예정 강의를 포함한 강의별 학습도 p의 `100 × (1 - sqrt(mean((1-p)²)))`다.
문제 미준비 강의는 계획상 p=0으로 가정하고 개수를 공개한다. 강의마다 같은 비중이다.
시험 시작 72시간 전을 목표 도달 시각으로 두고, 마지막 3일은 유지·밀린 분량 보충에 쓴다.
한국 자정 학습률 B와 오늘 끝 예상 학습률 F에서 하루 유지 비율 r을 추정한다(학습률 0이면 r=0.9 가정).
`B_next = r^dt × B + g × dt`를 목표일까지 전개해 하루 확보량 g가 일정하도록 푼다.
온전한 N일이면 `g=(T-r^N×B)×(1-r)/(1-r^N)`이며 r=1이면 `(T-B)/N`이다.
초반 순증가분은 크고 이후 망각 보충 비중이 늘어난다. 부분일은 dt로 비례 계산한다.
오늘 끝은 다음 자정과 목표 도달 시각 중 이른 시각이며, 여유 기간에는 시험 시작을 마감으로 쓴다.
자정 수준 이상을 유지하며 여유 기간에는 목표 미달분도 남은 시험 전 기간에 고르게 나누어 보충한다.
오늘 확보 목표는 `max(0, 오늘 끝 목표-F)`이며, 현재 기록을 오늘 끝까지 감쇠한 값과 목표를 비교해
남은 분량을 갱신한다. 평가 이력에서 자정 상태를 복원하므로 공부할 때마다 목표가 올라가지 않는다.
신규 평가에는 `dimension_before`와 `stability_after`를 함께 기록해 재현한다.
목표·시간표·문제은행이 바뀌면 계획도 갱신된다. 학습량은 %p이며 문제 수·소요시간 보장치가 아니다.
유지 비율은 매일 재추정하는 계획 근사로, 미래 복습에 따른 안정성 증가를 예언하지 않는다.
목표일 당일 이후 예정 강의와 공개 자료 상한을 표시한다. 늦은 공개·미달 누적 시 평탄한 학습량은 보장되지 않는다.

## 구조

| 경로 | 역할 |
|---|---|
| `app/main.py` | FastAPI 앱·라우터 연결 |
| `app/routes/` | 학생·관리자·러너·땡시 API |
| `app/models/` | 기능별 SQLAlchemy 모델과 공유 계약 |
| `app/jobs/` | 생성 작업 정책 |
| `app/srs.py` | 기존 퀴즈 복습 간격 |
| `app/study_engine/` | Quiz Bank 문항 선택·숙련도 |
| `app/cli.py` | DB 초기화·시간표 입력·운영 명령 |
| `app/config.py` | 환경 설정 |
| `app/storage.py` | R2·로컬 파일 저장 |

## 업로드와 배포

러너는 `RUNNER_TOKEN`으로 관리자 업로드 API를 호출한다.
서버에서 서명 URL을 받은 뒤 파일을 R2에 직접 PUT하고 업로드 완료를 알린다.
문항·메타데이터는 별도 API로 저장한다. 종류·파일 이름·반영 규칙은
[산출물 계약](../docs/artifact-contract.md)을 따른다.

운영 환경 값은 [.env.example](.env.example), 배포는
[배포 안내](../docs/deployment.md)를 참고한다.
`deploy.ps1` 실행은 운영 변경이며 Git push와 별도다.
