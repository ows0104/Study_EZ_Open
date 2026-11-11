# runner 작업 안내

명시적인 `parallelAuthoring=true`·CLI·source Main Quiz 요청은 문제은행·개념도·출제포인트를 독립 CLI 작업으로 동시에 처리한 뒤 기존 통합·원본/독립 정답 검수·최대3회 수정·업로드로 연결한다. `parallel_status.py`가 기존 status_batch의 개별 카드에 진행을 등록한다. 일반 bank/자동 쓸기의 웹 응답 대기 정책을 이 경로로 우회하지 않는다. 개별/전체 중지·취소와 원본/실패/사용량/수정 예산은 보존한다. 세부 실행·지정 강의 시범은 `docs/changes/2026-11-06-cli-parallel-main-quiz/`에 있다.
새 서버 요청은 `source-assessment/2-parallel/1`로 구분한다. 구형 러너의 기존 지원 형식 목록에 없는 값이므로 모델 호출 전에 중단한다. 배포 시 새 러너를 먼저 준비한다. 이미 시작한 /2 병렬 시범의 완료 증거는 기존 형식으로 검증하며 새 형식 요청으로 예산을 초기화하지 않는다.

`pipeline: map-tree/1` 요청(서버 형식 `source-assessment/2-map-tree/1`)은 Main-Quiz 시범 두 번의 앞 단계를 그대로 돈다. 근거는 `docs/changes/2026-11-09-main-quiz-runner-pipeline/`이다.
- `root_front.py`의 단계: 개념 지도 /3 → 포인트 /3 → 대조 → (지적이 있으면) 보완 1회·재대조 → 파생 packet
  - 출력 폴더: `runs/_root-generation/<gid>/front/`
  - 지시문: `content/prompts/learning-links/map-tree/`
- 생성기는 `<gid>/generation/`에서 파생 packet으로 돈다.
- 서버는 결과의 `manifest.derivedPacket`을 요청에서 다시 만들어 검증한다(`studyez_contracts.roots.map_tree`).
- 앞 단계도 자동 재실행하지 않는다. 관리자의 이유가 있을 때만 이어 간다(`--generation-resume <이유>` → `root_front --resume`). 그때 실패 단계와 그 뒤 단계를 `.resume-<k>/`에 보관하고 다시 돈다.
- 2026-11-11 안정화(`docs/changes/2026-11-11-pipeline-resilience/`, 이틀간 시작 13번 중 9번 보류):
  - 결과가 호스트 검사에서 거절되면 오류를 같은 세션에 한 번 되돌려준다(`Front.checked`). 거절된 파일은 `refused-<파일>`, 오류는 `check-failure.json`. 다시 거절되면 실패.
  - 문제은행은 생성기 접수와 같은 검사(`intake_rejections`)를 앞 단계에서 받는다. 문항에 속하지 않는 오류가 20분 뒤가 아니라 여기서 저자 세션으로 돌아간다.
  - 네트워크가 끊은 호출(`codex.network_failure`)만 연결을 기다려 한 번 다시 부른다(transport-retry/1). 남긴 파일은 `.net-<단계>/`. 시간 초과·콘텐츠 거절·사용량 한도·검사 실패·둘째 끊김은 지금처럼 멈춘다.
  - map-tree/2 이상은 포인트 → 대조 → 보완 → 재대조 한 줄이 지도·문제은행과 나란히 돈다. 하나가 실패해도 나머지는 끝까지 돌아 재개 때 다시 부르지 않는다.
- 기계 전체 Codex 동시 실행은 `studyez_llm.execution.slot`이 8로 묶는다(`STUDYEZ_CODEX_SLOTS`). 자리가 없으면 실패하지 않고 기다리며 로그에 `Codex 동시 실행 한도 대기`가 찍힌다.
- 2026-11-11 호출 시간 단축(`docs/changes/2026-11-11-pipeline-overlap/`, 세션 기록 101개 분해: 호출 시간의 절반이 입력 파일을 셸로 읽는 왕복):
  - 생성 단계의 첫 메시지에 `task.md`·스키마·`input.json` 내용을 싣는다(`root_native_json.inline_inputs`, 합 240,000바이트까지. 넘으면 지금처럼 파일을 읽는다). 파일·결과 파일·검사는 그대로다.
  - 앞 단계의 프롬프트는 `task.md`(불변) 뒤에 그 단계 입력 파일 내용을 붙인다(`root_front.inline_inputs`). 문제은행 단계는 여전히 포인트 산출물을 보지 않는다.
  - map-tree/3 앞 단계는 포인트가 확정되면 생성기의 `normalize`를 미리 부른다(`Front.early_normalize`, `--generation <gid>/generation`). 답은 `generation/.early/normalize.json`에 입력 지문과 함께 두고, 생성기가 차례에 지문이 같을 때만 쓴다(early-call/1, quizbank/CLAUDE.md). 이 호출의 문제는 앞 단계를 실패시키지 않는다.
- 이 변경 전의 러너는 이 요청을 모델 호출 전에 거절한다.

`root_native_json.py`는 `v3-`로 시작하는 root-generation/3 단계도 실행한다(스키마·프롬프트·단계 검사는 `studyez_contracts.roots.generation_v3`). 그 단계는 입력의 `pages`와 그 문항의 자극 그림만 첨부한다. /2 단계 이름의 동작은 그대로다. `pipeline: map-tree/2`(형식 `source-assessment/2-map-tree/2`)는 앞 단계에서 지도·포인트와 함께 독립 문제은행(`bank/`, 지시문 `parallel/bank.md` + `map-tree/bank-task.md`)을 동시에 뽑고, 파생 packet이 root-generation/3으로 돈다. 셋 중 하나만 다시 돌아도 다른 둘은 다시 돌리지 않는다. 마지막 포인트 대조에 남은 지적의 포인트는 `openPoints`로 결과까지 간다.

자료를 찾고 생성기를 실행한 뒤 결과를 서버에 올린다.
명시적 Concept map 자동출제 일감만 `connection_generation.py`로 분기한다. 서명된 원본 사본을 별도 인증 헤더 없이 받아
지문을 확인하고 생성기 하위 프로세스→결과 검증→조건부 게시를 수행한다. 작업 ID별 폴더와 수정 상한을 재사용한다.
명령은 [명령 안내](../docs/commands.md), 검사는 `python -m pytest tests/runner`다.
`powershell -ExecutionPolicy Bypass -File scripts/agent.ps1`는 실행 창에 로그를 표시한다.
이미 러너가 실행 중이면 새 일꾼을 만들지 않고 같은 창에서 현재 작업과 최근 로그를
20초마다 표시한다(Ctrl+C는 표시만 종료). 새 러너의 작업 로그는 단계가 같아도
20초마다 단계·전체 경과 시간을 출력하며, 하위 프로세스 출력 버퍼를 끈다.
숨김 실행 중인 러너는 `powershell -File scripts/runner-status.ps1`로 상태 창을 연다.
`powershell -File scripts/install-runner-desktop.ps1`은 바탕화면에 `Study EZ 러너` 바로가기를 만든다.
`pythonw -m runner.desktop`은 강의별 예습·복습 시작/중지/취소와 전체 일시정지를 제공한다.
창을 연 뒤 60초 동안 시작·취소 선택이 없으면 준비된 신규 작업을 기존 자동 상한 내에서 등록한다.
중지·취소·실패·완료 작업은 자동으로 되살리지 않으며, 전체 일시정지는 창을 닫아도 유지한다.
복습은 올해 필기와 저장된 웹 응답을 사용하는 기존 bank 후처리다. 구형 main 최초 출제는 하지 않는다.
로컬 선택은 `runs/desktop-control.json`에 보존한다. 중지는 산출물을 보존하여 held로 보고하고,
취소는 canceled로 보고한다. 전체 재개는 전체 일시정지로 보류한 줄만 풀며 개별 중지/취소는 유지한다.
로컬 로그·프로세스를 5초마다 읽고, 상태 창은 서버 대기열을 30초마다 읽기 전용으로 조회한다.
서버 조회는 `server/.venv` 런타임과 기존 DB 설정을 쓰며 실패 시 마지막 결과와 조회 실패를 표시한다.
콘솔 모드는 기존 로컬 기록만 표시한다.
상태 창(2026-11-11 개편, `docs/changes/2026-11-11-runner-status-ui/`): 실행 중 강의마다 카드 하나, 모두 스크롤 없이 보인다.
카드 = 강의명·경과 / 시간 비례 막대 / 남은 시간·완료 예상 시각 / 단계. Main-Quiz는 `status_phases.py`가
`runs/_root-generation/<gid>/` 파일 시각으로 6구간(지도·포인트 → 커버 확인 → 추가 출제 → 검토·수정 → 의학 검토 → 게시)과
지난 실행 12개의 구간별 중앙값으로 남은 시간을 낸다. 구간은 뒤로 가지 않는다. 막대는 경과 ÷ (경과 + 남은 시간)이고
예상이 없으면 막대도 숫자도 없다. 평소보다 길어지면 주황 막대와 「평소보다 길어지는 중」. 단계 수(`단계 i/n`)는 글자로만 둔다.
사용자 지시(2026-10-17): 상태 창에 `한 거 / 하는 거 / 할 거 / 확인 필요` 목록과 개수를
함께 표시한다 — 개수는 맨 위 한 줄, 목록은 「목록」을 눌러 펼친다. 일괄 작업의 모든 강의 상태를 읽고 반영 완료와 실패·상한 도달을 구분한다.
여러 강의를 동시에 처리하는 작업은 각 실행 강의를 별도 카드로 표시하며, 프로세스가 종료되면
미완료 실행 상태를 실행 중으로 표시하지 않는다. 완료 이력은 종료 후에도 남긴다.
왕복 애니메이션과 초 단위 카운트다운은 쓰지 않으며, 원본 로그·내부 단계 이름은 `상세 기록`에서 펼친다.
Main-Quiz가 아닌 작업의 예상 시간은 서버 etaSeconds, 없으면 최근 2일의 같은 과목·작업 종류 완료 기록 중 3분~3시간 실행의 중간 50% 범위다.
재처리 여부가 같은 표본을 우선하고, 3개 미만이면 같은 종류를 사용한다. 2개 일꾼의 대기 순서도 반영한다.
표본 부족·평소 범위 초과 시 숫자를 만들지 않고 계산 대기·지연으로 표시한다.
창을 닫아도 기존 러너는 계속 실행된다. 텍스트 표시는 `-Console`, 한 번만 확인은 `-Once`다.
상태 창은 기본 설치의 `pythonw.exe`로 직접 연다. uv 가상환경의 프록시는 검은 콘솔을
추가로 띄울 수 있으므로 `pyvenv.cfg`의 `home` 아래 실행 파일을 사용한다.
다른 세션의 검수는 `runs/status-jobs/*.json`에 `id`, `label`, `owner`, 프로젝트 상대 경로
`script`·`log`·`outputs`, 강의 ID별 제목 `targets`를 등록하면 같은 창에서 표시된다.
고정 강의 작업은 `run_id`도 지정한다. 실행 중인 프로세스로 활성 여부를 판단하며,
복원·메타데이터 작업은 `activity: metadata`, `state_file`, 상태별 표시 문구 `stages`로 구분한다.
로그가 조용하다는 이유로 중단·실패를 표시하지 않는다. 시작 기록만 남은 작업은 실행 중으로 세지 않는다.
창 없는 새 작업은 `python -m runner.background --cwd <작업 폴더> --log <로그> -- <명령> <인수>`로 연다.
러너와 CLI의 하위 프로세스도 Windows `CREATE_NO_WINDOW`로 실행하며 검수 규칙은 바꾸지 않는다.
중첩 CLI의 단계 출력은 표준 입력·출력·오류 핸들을 명시해 러너 로그에 전달한다.
현재 로그가 조용하면 실행 중인 CLI의 `--out` 안에서 새 산출물만 관측해 표시한다.
이 표시는 `산출물 확인`으로 구분하며, 이전 시도 파일이나 산출물 존재만으로 완료를 판정하지 않는다.

## 수정 위치

| 책임 | 파일 |
|---|---|
| CLI 옵션·분기 | `cli/` (`__main__.py`는 진입점) |
| 자료·강의 이름 | `filenames.py`, `watch.py`, `matching.py`, `blocks.py` |
| 실행 사이클·일꾼·중단·잠금 | `cycle.py`, `agent.py` |
| 로그 판정·재개 시각·인증 재시도 기록 | `agent_state.py` |
| quizgen 접점·계약 변환 | `deck.py` |
| Quiz Bank 처리·직접 업로드 | `bank_flow/CLAUDE.md` — `bank.py`는 기존 진입점 |
| 업로드·보류 판정 | `publish.py`, `gate.py` |
| 공통 HTTP·서명 파일·전송 재시도 | `transport.py` — publish의 기존 이름도 유지 |
| 시도 위치·선택 | `runlayout.py`, `chosen.py`, `attempts.py` |
| 원본 판·내용 지문 | `fingerprint.py` |

## 지켜야 할 동작

`agent.py`는 실행·하트비트·중단·잠금을 소유한다. `agent_state.py`는 로그 해석과
대기/재시도 기록을 소유한다. `publish.py`는 게시할 자료 선택·보류·ledger,
`transport.py`는 HTTP와 파일 전송만 맡는다. 전송 모듈에서 생성기나 일감을 실행하지 않는다.
보존 검사와 기능별 시작 파일은 `bank_flow/CLAUDE.md`에 있다.

2026-10-18 사용량 개선: 공통 Codex 어댑터는 동일 cwd·입력·모델·스키마의 동시 요청을
파일 잠금으로 차단한다. 실패·시간 초과에도 잠금을 해제하며 시간 초과 시 CLI 자식 트리도 종료한다.
호출별 카운터는 `runs/_llm/usage/<UTC날짜>/*.json`에 남긴다(본문·인증값은 저장하지 않는다).
완료 카운터가 없는 실패 사용량은 0으로 간주하지 않고 미상으로 표시한다.
`.venv/Scripts/python.exe scripts/codex_usage.py`로 모델 호출 없이 집계한다.
로컬 입력·계약 오류를 문항 저작 재시도로 넘기지 않고 먼저 검증한다. 모델·필수 원본 검수·
독립 검수와 기존 수정 상한은 사용량 최적화를 이유로 낮추거나 우회하지 않는다.

학습현황의 약리학 퀴즈 준비 현황은 `share_monitor.py`가 공개 공유 링크를 5분마다
검증한다. 러너 시작 시 함께 실행하며 공개 링크의 완성 응답 작성 시각을 서버에 기록한다.
2026-10-15 00:00 KST 이상인지와 완성 퀴즈 업로드 시각을 별개로 표시한다.
현재 러너를 재시작하지 않고 붙일 때는 `python -m runner.share_monitor`를 숨김 실행한다.

2026-10-17 사용자 지시: ChatGPT 브라우저를 열지 않고 저장된 공개 공유 링크에서 본문을
비로그인 HTTP로 회수한다(`shared_bank.py`). `bank --import-share`는 저장·등록만 수행한다.
새 공유 링크 저장은 자동으로 회수 작업을 등록한다. 강의 ID·완료 표식·문항 ID를 검증하고,
같은 게시 응답은 재검수를 생략한다. 실제 원문·공유 URL·응답 시각이 바뀌면 덮어쓰지 않는다.

2026-10-16 저녁 사용자 지시: `bank`는 저장된 완성 웹 응답만 처리하고 없으면 웹 출제 대기로
남긴다. 자동 CLI 최초 출제는 하지 않는다. `--web-postprocess`로 별도 포인트·보기·해설 작성과
자동 내용 수정 반복을 생략하며 원본·정답 검수·유효 웹 근거 재사용·업로드는 유지한다.
구형 웹이 보내는 `points` 일감은 별도 추출 생략을 명시하고 마친다. 기존 독립 캐시는 보존한다.
아래 `points` 준비 설명은 명시적으로 독립 추출기를 사용하는 과거 경로의 계약이다.

- `deck.py`가 quizgen 접점을 맡고, `bank.py`는 quizbank를 하위 프로세스로 실행한다.
- `points` 일감은 `runner bank --points-only`로 원본 독립 포인트만 준비하며 문항 생성·업로드는
  하지 않는다. 완료 목록과 출처 이력은 `runs/<편>/bank/`에 보존하고 본 처리에서 재사용한다.
- 덱 성공은 종료 코드와 이번 실행 산출물을 함께 본다. 마지막 요약 출력도 실패할 수 있다.
- `BUILDING`·러너 잠금·업로드 직렬화는 같은 강의를 겹쳐 만들거나 반쪽 결과를 올리지 않게 한다.
- 세션 한도·동기화 대기는 재개 시각을 기록한다. 인증 거절은 재시도 상한이 있고 실패와 구분한다.
- 예습 링크의 원본은 서버다. 업로드 전에 동기화하고, 대화와 덱이 어긋나면 예습 덱을 보류한다.
- 누락·보류·하루 상한은 합계와 이유를 보고한다. 모두 같은 0으로 숨기지 않는다.
- 러너는 시간표로 이번 블럭의 대상 과목을 확인한다. 읽기 실패·블럭 없음·과목 없음이면
  업로드와 일감 처리를 중단하며 전체 과목으로 넓히지 않는다. 범위 밖의 일감은 보류한다.
  배포 사본에서는 `agent --timetable <원본 시간표 경로>`로 시간표 위치를 명시한다.
  예외는 서버 claim이 실제 버튼 작업·수신 완료 RootGeneration에 연결해 준 rootGenerationId뿐이다.
  이 요청은 해당 ID만 CLI로 전달해 현재 블럭 밖 강의도 처리한다. 일반 작업·자동 쓸기의 과목 범위,
  시간표 미확인 시 중단·개별/전체 중지·취소와 검수 상한은 그대로 유지한다.
- `watch.DEFAULT_MAX_ITEMS` 같은 운영 상한은 사용자 결정 없이 바꾸지 않는다.

## 자료·시도 계약

예습 원본은 `preview_sources.History`가 최근 5년의 동일 강의·동일 교수 최신 보유 필기로 고른다.
없으면 확인된 작년 자료를 사용한다(2026-11-05 사용자 승인). publish/readiness/prequeue와
데스크톱 준비 판정이 이 선택과 공통 대화 출처 검사를 공유한다. `_pairs`·합본 범위는 보존한다.
게시 전 서버 `/api/admin/previews`의 `previewSourceVersion: 1`을 확인한다. 준비되지 않은
구형 서버에는 새 교수 선택에 따른 강의·첨부 변경을 보내지 않는다.
원본이 바뀐 기존 대화/덱을 자동으로 새 필기에 귀속하거나 재출제하지 않는다.
`ahead.plan(include_unmatched=True)`는 자료가 없는 시간표 자리의 확인 필요 요약도 만든다.

파일명은 NFC 정규화 후 해석하며 `run_id`와 강의의 실제 식별자 `uid`를 구분한다.
선택교과 등 제외 대상은 `filenames.py`가 정의한다. 파일을 못 읽으면 이유를 보고한다.

보존 대상·현재 시도 선택은 `runlayout.py` 한 곳에서 정한다.
사람의 `HOLD`·`CHOSEN.json`·`preview.md`·`note.md`·연도 매칭 기록을
재생성 가능한 파일로 취급하지 않는다. [runs 구조](../docs/runs-layout.md)를 따른다.

`chosen`은 카드 해시와 사용자가 적은 이유를 기록한다. 선택한 카드와 배포 카드가
어긋나면 덱을 보류한다. `promote`는 선택한 결과를 배포 위치로 옮긴다.

## 족보

새로 정리·첨부하는 족보는 [공통 PDF 형식](../docs/policies/jokbo-attachments.md)을 따른다.
JSON·그림은 관리용으로 보존하고 검증된 교수우선 PDF를 첨부한다.

원본 없음(`absent`)과 원본이 있지만 미분할(`uncut`)을 구분한다.
미분할은 준비가 필요하며, 교수 변경으로 올해 출제분이 0인 경우와도 다르다.

컷은 `runs/_materials/<과목>/<판>/`에 둔다. 분할에는 과목 폴더,
생성기의 `--jokbo-dir`에는 컷 판 폴더를 전달한다.
옛 `_jokbo` 경로는 과거 설정을 재개할 때 여전히 읽을 수 있어야 한다.

현재 족보와 옛 판은 목차 제목으로 합치며 중복 연도는 추가하지 않는다.
올해 교수는 실제 필기 파일명 또는 예습 대상에서 읽는다.
`pack.find_jokbo`가 올해 교수 문항과 참고 문항을 나누므로 모든 생성 경로가 이를 공유한다.
정답 키가 겹치면 연도·번호뿐 아니라 강의 머리로 구분한다.

사례는 [runner 기록](../docs/archive/runner-cases.md),
최근 족보 결정은 [변경 전 문서](../docs/archive/2026-10-06-originals/runner/CLAUDE.md)에 있다.
