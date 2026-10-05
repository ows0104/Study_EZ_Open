# quizgen 사용·수정 안내

강의 PDF를 예습·복습 카드와 Anki 덱으로 변환한다.
모델 단계는 로그인된 `claude` CLI의 빈 세션으로 실행하며, 로컬 파일 처리와 검증은 Python이 맡는다.
원본 자료를 서버에 배급하는 작업은 `runner`의 책임이다.

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
