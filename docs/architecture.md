# 현재 구조

Study_EZ는 예습·복습 덱과 Quiz Bank를 제공한다. Spotter는 사진 기반 땡시 앱이다.
두 앱은 서버의 인증·DB·파일 저장소를 공유한다.

## 역할과 데이터 흐름

```text
로컬 자료: Synology PDF · 시간표 · 예습 대화
                    ↓
runner: 탐색·매칭 → 서버의 생성 작업 수신
        ├ quizgen: PDF → 카드 → 검사·수선 → Anki 덱
        └ quizbank: ChatGPT 답 → 정리 → 구조 검증 → 외부지식 검토
                    ↓
       파일은 R2, 메타데이터·작업 결과는 server
                    ↓
       web / spotter: 인증된 사용자의 자료 열람·학습
```

서버에는 생성 작업 큐가 있다. 실제 모델 호출과 PDF 처리는 로컬 러너가 수행한다.
두 생성기는 `studyez_llm/codex.py`를 통해 ChatGPT 로그인된 Codex CLI의 GPT를 호출한다.
모델 선택·설정은 [GPT 실행 설정](quizgen.md#gpt-실행-설정)을 따른다.
`runner agent`는 작업 실행과 주기적 업로드를 관리하고, 진행·실패·대기를 서버에 적는다.
운영 상한·재시도 정책은 해당 코드에 있으며 문서에 숫자를 따로 복제하지 않는다.

## 세 가지 학습 자료

| 자료 | 입력 | 생성·처리 | 이용 |
|---|---|---|---|
| Main-Quiz (Quizbank) | 올해 필기·족보로 만든 ChatGPT 답 | `quizbank.run` | Study Engine이 다음 문항 선택 |
| Pre-Quiz | 작년 필기·예습 대화 | `quizgen.prequiz.run` | 웹 자기채점·Anki |
| 기존 Main-Quiz | 전환 전에 생성한 카드·덱 | 새 생성 중단 | 기존 웹 기록·Anki 덱 보관 |

2026-10-06부터 Main Quiz는 Quizbank로 생성한다. 필기 업로드만으로 quizgen 작업을
등록하지 않는다. ChatGPT에서 출제한 완성 답을 저장하면 `kind=bank` 작업으로 정리·검증한다.
공개는 관리자가 결정하며, Pre-Quiz의 생성과 기존 카드·학습 기록은 유지한다.
관리자의 완료 체크는 Quizbank 검증·학생 공개를 기준으로 한다. 기존 Main 덱의
해당 없음 표시는 새 문제은행에 승계하지 않는다. DB 스키마 변경은 없으며 배포는
서버 → 웹 → 로컬 러너 재시작 순서로 적용한다.

Quiz Bank의 최초 문항 생성 프롬프트는 `web/src/bank/bankPrompt.md`다.
확장은 PDF와 족보 조각을 대화에 붙이고 답을 회수한다. `quizbank`는 받은 답을
정리하고 구조를 검사한다. 특정 문항 오류는 해당 문항을 제거하고 다시 검사하며,
전체 구조 오류는 공개를 막는다. 외부지식 검토 결과는 표시로 남긴다.

기존 웹 퀴즈의 복습 간격은 `server/app/srs.py`, Quiz Bank 문항 선택은
`server/app/study_engine/`이 담당한다. 서로 다른 학습 방식이므로 별개로 유지한다.

## 경계

- 서버는 `runner`·`quizgen`·`quizbank`를 import하지 않는다.
- 러너는 `deck.py`에서 quizgen 계약을 연결하고, quizbank는 하위 프로세스로 실행한다.
- 클라이언트 간 직접 호출 대신 서버 HTTP API를 사용한다.
- 파일 계약은 [artifact-contract.md](artifact-contract.md), 작업 폴더는 [runs-layout.md](runs-layout.md)에 있다.
- 공용 세션 원본은 `platform/session/session.js`다. Spotter는 동기화한 사본을 사용한다.

## 서버와 공개 범위

Supabase는 로그인·Postgres, R2는 비공개 파일, Cloud Run은 API,
Cloudflare Pages는 웹을 담당한다. 서버는 승인·관리자 권한을 검사한 뒤 파일의
서명 URL을 발급한다. 업로드 본문은 서명 URL을 통해 R2로 직접 전달된다.

Main-Quiz와 Pre-Quiz는 각각 `/mainquiz/:subject/:runId`와
`/prequiz/:subject/:runId`에서 풀 수 있다. `/bank/:subject/:runId`도 같은 Quizbank를 연다.
Main Quiz는 관리자가 공개한 강의만 학생에게 보인다. 기존 카드 풀이는
`/legacy-mainquiz/:subject/:runId`에서 이어간다. 기존 `/api/…/mainquiz`는 보관 카드 API다.
강의 키는 서버에서 `(subject, run_id)`로 다룬다.

## 배포와 검토

`runner/gate.py`는 파일·메타데이터·선택한 시도·사용자 보류 표시가 일치하는지 확인한다.
배포가 보류되어도 강의록만 먼저 올라갈 수 있다. 카드 결함 표시는 관리자 검토로
전달되므로, `.apkg` 존재만으로 모든 품질 검사가 통과했다고 판단하지 않는다.

웹 push와 API 배포는 별도다. 구체적인 절차는 [배포 안내](deployment.md)에 있다.
과거 구조·실패 실측은 [기록 보관함](archive/README.md)에서 필요할 때 확인한다.
