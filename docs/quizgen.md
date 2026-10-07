# quizgen 사용·수정 안내

현재는 Pre-Quiz 카드와 Anki 덱을 생성한다. Main Quiz는 Quizbank로 전환했으며
`quizgen.run`과 `runner watch --build`의 기존 Main 생성은 중단한다.
아래 Main 관련 설명은 기존 산출물과 내부 코드의 유지보수 참고다.
모델 단계는 ChatGPT 계정으로 로그인된 `codex` CLI의 빈 세션으로 실행하며, 로컬 파일 처리와 검증은 Python이 맡는다.
원본 자료를 서버에 배급하는 작업은 `runner`의 책임이다.

## 예습 난도 구성

새 예습은 총 8~12문항에 기본·심화·도전을 모두 포함한다. 10문항이면 기본 5·심화 3·도전 2를
출발점으로 삼되 자료에 맞춰 조정하며 도전은 1~2문항이다. 기본은 핵심 확인, 심화는 기전·비교·
한 단계 적용, 도전은 여러 관계를 연결하는 추론이다. 기본→심화→도전 순서로 배치한다.
예습 설명본이 있으면 기본·심화 문항의 답을
그 안에서 도출할 수 있어야 한다. 원문 발췌의 존재는 코드가 대조하고, 실제로 답을
뒷받침하는지는 관리자 검토에서 확인한다. 설명본이 없으면 읽기 확인을 보장하지 않는다.

`learning_support`는 난도(`difficulty`: basic·advanced·challenge), 접근 힌트(`hint`), 지금 알아둘 범위(`scope`), 수업에서 들을
질문(`lecture_focus`), 관리자용 예습 원문(`preview_excerpt`)을 담는다. 학생 앞면에는
난도와 힌트를 보내며, 범위와 수업 질문은 답을 펼친 뒤에 보인다. 원문 발췌는 학생 API에 싣지 않는다.
웹의 세 난도 모두 같은 진행·이해 확인을 사용한다. 「이해했어요」·「아직 헷갈려요」 어느 쪽을
골라도 한 번만 진행한다. 후자는 완료 화면에 답과 설명이 남는다. 예습은 복습 날짜를 잡지 않으며,
기존에 저장된 복습 시각도 무시한다. 「다시 훑어보기」는 기록을 지우지 않고 선택을 갱신한다.
웹과 Anki는 질문 접두어 대신 난도 배지를 표시한다. Anki에는 난도 태그도 붙인다.
기존 문항의 기본·심화 난도는 자동 추정하지 않으며, 새 분류는 재생성부터 적용한다.
난도는 기존 `learning_support` JSON에 저장하므로 이 변경에 DB 칼럼 추가는 필요 없다.

배포 시 서버 `init-db`로 `pre_item`·`main_item`의 `learning_support` 칼럼을 추가한 뒤
API와 웹을 배포한다. 기존 카드는 빈 지원 정보로 호환되며, 새 문구·문항 수는 재생성부터
적용된다. 예전 10~15문항 생성 작업을 재개하면 새 분량 계약에 맞춰 목표를 다시 골라야 한다.

UI 확인: `web`에서 Vite를 실행하고 `/tests/prequiz.html`을 연다. 모든 API는 메모리로
대체되며 실제 학습 기록을 전송하지 않는다.

## GPT 실행 설정

`codex login`으로 ChatGPT 계정에 로그인한다. CLI 0.160.0에서 검증했으며
`exec --ignore-user-config`·`--ignore-rules`·`--output-schema`를 지원해야 한다.
CLI 옵션과 JSONL 이벤트는 [공식 비대화형 실행 문서](https://learn.chatgpt.com/docs/non-interactive-mode)를 참고한다.

- 기본 모델: `gpt-6.1-sol`. `--model` 또는 `STUDYEZ_MODEL`로 바꾼다.
- 재현 의미 채점: `gpt-6.1-sol`. `--judge-model`로 바꾸며, 명시적 `--model`이 우선한다.
- 실행 파일이 PATH에 없으면 Windows Codex 앱의 번들 CLI를 자동으로 찾는다.
  다른 설치 위치는 `STUDYEZ_CODEX_BIN`에 Codex 실행 파일 경로를 지정한다.
- 기존 `opus`·`sonnet`·`STUDYEZ_CLAUDE_BIN` 설정은 사용하지 않는다.
- 사용자 설정·MCP·브라우저·메모리를 끄고 실행한다. 재현 검사는 shell·이미지 도구도 끄며
  매번 별도 임시 폴더에서 실행한다. 기존 canary 파일 차단 검사를 유지한다.
- 저작은 workspace-write sandbox에서 shell·view_image로 자료를 읽고 파일을 쓴다.
  Windows에서는 Codex의 elevated sandbox 구현을 명시한다.
  PDF는 `studyez_llm/pdf.py`로 지정한 쪽을 렌더한다. 기존 `Read(...)` 표기는
  `quizgen/session.py`가 Codex용 읽기 지시로 해석하도록 안내한다.
- 토큰과 모델은 기존 사용량 원장에 기록한다. Codex CLI가 달러 비용을 제공하지 않으므로
  비용은 미상이며 기존 표의 `·`/0은 실제 무료 또는 청구액 0을 뜻하지 않는다.

Quiz Bank 정리·외부지식 검토도 같은 Codex 실행 어댑터를 사용한다.
로그인 계정·CLI 경로를 바꾼 뒤에는 실행 중인 `runner agent`를 다시 시작한다.
기존 생성물은 유지되며 새로 실행하는 모델 단계부터 GPT가 사용된다.

## 직접 실행

```powershell
python -m quizgen.run "<올해 필기.pdf>"
python -m quizgen.run --resume "<작업폴더>"
python -m quizgen.prequiz.run "<작년 필기.pdf>" --note "<예습대화.md>"
python -m quizgen.prequiz.run --resume "<예습 작업폴더>"
```

정확한 옵션은 각각 `--help`로 확인한다.
`--out`은 새 출력 위치, `--resume`은 기존 시도 이어하기다.
러너는 강의 식별자와 배포 계약을 맞추므로 운영 강의는
[runner 명령](commands.md)을 통해 실행하는 편이 편하다.

## 흐름

| 단계 | 복습 | 예습 |
|---|---|---|
| 자료 준비 | `prep.py`, `pack.py` | 공용 자료 처리 + 예습 대화 |
| 출제 계획 | `plan` | `must_know` |
| 카드 생성 | `assemble.py`·프롬프트 | `prequiz/`·프롬프트 |
| 검사·수선 | 구조 검증, 재현·누출 검사, 수선 | 예습 계약 검증, 재현 검사, 수선 |
| 덱 생성 | `build.py`·`anki_models.py` | 공용 덱 생성 + 예습 계약 |

단계 순서와 재시도는 `run.py`·`prequiz/run.py`, 공통 실행 처리는 `runbase.py`에 있다.
산출물 필드는 [산출물 계약](artifact-contract.md), 시도 위치는 [runs 구조](runs-layout.md)를 본다.

## 수정 위치

| 바꾸려는 것 | 파일 |
|---|---|
| 출제 판단·말투·자료 해석 | `prompts/core/`, `profiles/`, `adapters/`, `domains/` |
| 특정 단계의 지시 | `prompts/plan.md`, `cards.md`, `repair.md` 등 |
| 예습 단계 지시 | `prequiz/prompts/` |
| 프롬프트 조립 순서 | `prompting.py` |
| 기계가 확인할 구조·플래그 | `validate.py`, `prequiz/validate.py` |
| 질문만 보고 답 재현 | `reproduce.py` |
| PDF 판 변경·카드 재사용 | `slidediff.py`, `revise.py` |
| 카드 HTML·패키징 | `build.py` |
| Anki 모델·CSS | `anki_models.py` |

[프롬프트 조립 구조](prompt-architecture.md)와 [작업 규칙](../quizgen/CLAUDE.md)을 함께 본다.

## 결과를 해석할 때

- `.apkg`가 있어도 결함 표시가 남을 수 있다. `run.meta.json`과 검토 결과를 확인한다.
- 이전 실행의 파일과 이번 실행의 결과를 구분한다. `--force`·재개 시 산출물 선택 규칙을 유지한다.
- 재현 일치율 하나로 문항 품질을 판단하지 않는다. 자명한 문항도 재현 검사를 통과한다.
- 프롬프트 비교는 새 생성 한 편의 비율보다 같은 표본에 대한 가림 평가를 사용한다:
  `python -m quizgen.judge cloze <시도A> <시도B>`.
- 모델 평가·새 덱 생성에는 실제 호출이 발생한다. 코드 검사는 `python -m pytest tests/quizgen`으로 한다.

설계·실패의 상세 기록은 [quizgen 사례](archive/quizgen-cases.md),
[인터뷰](archive/interview.md), [변경 전 안내](archive/2026-10-06-originals/docs/quizgen.md)에 있다.
