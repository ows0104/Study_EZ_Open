# 산출물 계약

로컬 생성기와 서버 사이의 현재 계약을 찾는 문서다.
필드의 정본은 `runner/deck.py`·`quizbank/schema.py`와 해당 서버 라우트다.
예시는 [samples](samples/README.md), 작업 위치는 [runs 구조](runs-layout.md)를 본다.

## 강의 식별자

| 이름 | 의미 | 담당 |
|---|---|---|
| `uid` | 날짜·교시·제목 어간·교수로 강의를 구별 | `runner/filenames.py` |
| `run_id` | 실행 자료의 강의 ID. 예: `261005_01` | `runner/filenames.py` |
| `(subject, run_id)` | 서버에서 강의를 찾는 키 | `server/app/models/` |
| `deck_id` | Anki GUID 씨앗. 예: `p261005_01` | `runner/deck.py` |

같은 날짜·교시에 강의가 여러 개일 수 있으므로 `run_id` 생성 규칙을 유지한다.
강의 파일명·제목은 NFC 정규화 후 처리한다.
Anki 표시 이름과 GUID 씨앗은 다르다. 표시 이름 변경을 이유로 GUID를 바꾸지 않는다.

## 배포 파일

| 파일 | 생산자 | 소비자 |
|---|---|---|
| 올해·작년 PDF | 원본 자료·러너 | 서버 자산 API |
| `*.apkg` | quizgen·러너 | Anki 다운로드·`gate` 검사 |
| `run.meta.json` | `deck.contract` | 복습 관리자 화면·`gate` |
| `pre_run.meta.json` | `deck.contract` | 예습 관리자 화면·`gate` |
| `main_items.final.json` | `deck.contract` | `PUT …/main-items`·웹 복습 |
| `pre_items.final.json` | `deck.contract` | `PUT …/pre-items`·웹 예습 |
| `slides/<run_id>_sNNN.png` | 러너의 슬라이드 내보내기 | 웹 퀴즈 근거 이미지 |
| Quiz Bank JSON·쪽 PNG | `quizbank`·`runner/bank.py` | 은행 API·Study Engine |

복습 슬라이드 kind는 `main_media`, 예습은 `media`다.
같은 쪽번호여도 서로 다른 PDF일 수 있으므로 합치지 않는다.
추가 자산 kind의 정본은 서버 모델에 있다.

Quiz Bank 1.76부터 중추신경계 `261006_02`·`261006_03`는 실제 UTF-8
`study-ez-<run_id>-bank.md` 파일을 전달한다. 첫 줄의 `STUDYEZ_BANK_FILE` JSON은
schema_version·subject·run_id·prompt_version·question_count·question_ids·conflict_ids를 기록한다.
모든 문항·출처 충돌 뒤 마지막 줄에만 `STUDYEZ_BANK_COMPLETE`를 둔다.
사이트·브리지는 파일을 읽어 구조를 검사하고, `/bank-response`에는 원문과
`responseFile: {filename, sha256, byteLength}`를 전달한다. 서버와 러너가 다시 검사하며,
러너는 받은 바이트를 `raw.md`, 검증 정보를 `response-file.json`에 보존한다.
파일 검사는 전달·구조 검증이며 원본·정답 검수를 대신하지 않는다. 기존 은행·학습 기록은 유지한다.

덱 이름은 강의 ID·제목·교수를 사용하고 예습에는 ` 예습`을 붙인다.
예습은 과거 자료로 만들어도 올해 대상 강의의 표시 이름을 사용한다.
대상 정보는 `pre_target.json`이 연결한다.

`notes_prev` kind는 호환을 유지하되 실제 원본은 최근 5년 중 동일 교수의 최신 보유 필기다.
없으면 확인된 작년 자료로 돌아간다. `previewSource` v1 공통 계약은
`studyez_contracts/preview_sources.py`이며 단일 선택기는 `runner/preview_sources.py`다.
올해 담당/출처, 작년 비교, 검색/미보유/실패 연도, 선택 연도/교수/파일/해시를 보존한다.
학생 응답은 관리용 경로/보존본 키를 제외하고 캘린더·상세에 같은 요약을 준다.
새 메타데이터를 생략하는 구형 러너는 기존 값을 지우지 않는다.

교수 기준 예습 필기는 선택 해시별 객체 키를 사용한다. 교체 전 이전 객체는 삭제하지 않고
Lecture JSON의 `_previousAttachments`에 파일·객체 키·바이트 해시·크기·복원 정보를 보존한다.
선택 이력과 공유 대화의 원본 연결도 내부 JSON으로 보존한다. 원본과 대화가 어긋나면
새 원본으로 기존 대화를 자동 재사용하지 않으며 확인된 새 링크 전까지 Pre-Quiz 생성을 보류한다.
운영 `lecture.preview_source` nullable JSON 준비 및 구체 자료 전환은 별도 중요 승인 대상이다.

## 덱 메타데이터

`run.meta.json`의 `lecture_id` 값은 `run_id`다.
주요 필드는 다음 역할을 한다. 예습도 대응하는 `pre_run.meta.json`을 사용한다.

| 필드 | 의미 |
|---|---|
| `deck_id`, `deck_name`, `deck_file` | 덱 식별·표시·파일 |
| `attempt` | 생성 시도의 kind·판·카드 해시. 옛 구조에서는 없을 수 있음 |
| `verified` | 패키지를 다시 열어 센 노트·카드·미디어와 누락 |
| `item_count` | 계약이 주장하는 노트 수 |
| `format`, `sources`, `importance` | 구성별 개수 |
| `review_flags`, `reproduce_defects` | 관리자 검토 표시 |
| `reproduce` | 답 재현 결과 분포 |
| `web_items`, `web_excluded`, `slides_exported` | 웹 변환 결과 |
| `strategy`, `strategy_why` | 복습 전략과 이유 |

`item_count`와 패키지 실측이 다르거나 미디어가 없으면 배포 보류 사유가 된다.
재현 불일치·품질 표시 개수를 같은 의미로 취급하지 않는다.
현재 흐름은 결함 표시를 남긴 채 덱을 제공하고 관리자에게 검토를 요청할 수 있다.

## 웹 퀴즈

웹 계약의 항목은 `id`·`qtype`·`stem`·`answer`·`explanation`과
근거·표시·슬라이드 정보를 포함한다. 기존 자유회상 퀴즈는 사용자가 답을 보고 자기채점한다.
답과 해설은 처음 문항 목록에 포함하지 않고 reveal 요청으로 제공한다.

`basic`·`cloze`·`ox`가 웹 변환 대상이며 그림 카드 제외 수는 메타데이터에 남긴다.

Quiz Bank는 `GET …/bank/anki`에서 전체 문항을 `.apkg`로 내보낸다. 빈칸을 포함한
8가지 형식은 문항당 앞뒤 카드 한 장으로 제공하며, 정답·출처·자료 충돌·외부지식 검토와
인용한 `bank_media`를 담는다. 이미지가 누락되면 다운로드를 보류한다.
은행·검토·이미지의 내용별로 R2에 캐시하고 공개 설정을 확인한 뒤 서명 URL을 발급한다.
Main 모아받기는 사용할 수 있는 Quiz Bank 덱을 우선하며, 없으면 기존 `main_apkg`를 제공한다.
`exportId`로 다운로드 중 판 변경을 확인하고, 다운로드 기록도 판별로 구분한다.
Anki의 복습 일정과 웹 학습 기록은 서로 독립적이다.

Main-Quiz 단답·나열 문항의 「선지 보기」 선지는 `root_choices` kind의 `<revision>.json` 하나다(`root-choices/1`,
`quizbank/root_choices.py`, 계약 `studyez_contracts/roots/choices.py`). 러너가 근거 보강 뒤에 판 문서의 글만으로 만들어 올린다.
서버는 revision과 문항 지문이 맞는 문항에만 붙이고, 없으면 선지 없이 보여 준다.

Main-Quiz 판의 근거 보강은 `root_evidence` kind의 `<revision>.json` 하나다(`root-evidence/1`,
`quizbank/root_evidence.py`). 러너가 판 게시 뒤 같은 고정 원본으로 만들어 올린다. 서버는 revision과
원본 지문이 맞을 때만 읽어 핵심 슬라이드·족보 지면·근거 상태를 붙이고, 없으면 인용 쪽만 쓴다.
학생 파일 목록(`DOWNLOADABLE`)에 들지 않으며 작업을 만들지 않는다.
Anki의 cloze 문법은 웹용 빈칸으로 변환한다.
예습과 복습 문항은 각각 다른 kind로 저장하고, 복습 간격은 서버 `srs.py`가 정한다.

예습의 `why_tags` 배지는 앞면에, `why_asked` 이유 글은 답 뒤에 표시한다.
기존 JSON 표본은 전체 최신 선택 필드를 망라하지 않으므로 실제 계약 변환 코드도 확인한다.

## 예습 링크와 Quiz Bank

예습 링크는 서버가 원본이다. 러너가 저장된 주소를 받아 로컬 대화와 동기화한다.
제공자·URL 검증은 `server/app/preview_links.py`에서 처리한다.
공유 주소와 원 대화 주소는 별도 필드이며 학생에게 원 대화를 노출할지는 서버 설정을 따른다.

Quiz Bank는 `quizbank/schema.py`의 구조·`validate.py`의 규칙을 따른다.
정리 결과, 제거 문항, 외부지식 검토, 출처 충돌, 근거 슬라이드를 보존한다.
사용자별 학습 상태는 `bank_state`, 신고는 `bank_feedback`으로 별도 저장한다.

CLI 생성·독립 포인트 실행의 `runtime.json`은 실제 실행 사본 경로, 공통 프롬프트 버전·hash와
주요 코드 hash를 시작·완료·실패 시점별로 남긴다. 웹 응답의 출제 버전과 별개이며, 시작 기록만으로
실행 성공을 판단하지 않는다. 실행 중 계약이 달라지면 `contractUnchanged`가 false다.

기존 퀴즈 학습 기록·카드 수정·이용 기록도 사용자별로 저장된다.
공용 학습 자료와 개인 상태를 같은 데이터로 덮어쓰지 않는다.

## 변경 시 확인

파일 계약을 바꾸면 생산자(`runner/deck.py` 또는 `quizbank`),
소비자(서버 라우트·웹 타입), 표본과 관련 검사를 함께 확인한다.
서버 업로드는 서명 URL 발급 → 파일 PUT → 완료 확인 순서이며
Content-Type과 파일 종류를 요청 계약대로 유지한다.
