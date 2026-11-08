# Measure recall load and structural answer cues in the bank checker — 구현 계획

## 변경 범위·대상 파일·순서

1. `studyez_contracts/bank/quality.py` — 선 상수, `answer_polarity`, `recall_chars`,
   `_yes_no_axis`, `_polarity_bias`, `_overstated_cue`, `_recall_load`, `_narrow_format`
   를 더하고 `quality_errors` 가 문항별·은행별 경고를 모은다. errors 경로는 그대로.
2. `tests/quizbank/test_answer_quality.py`(새 파일) — 측정별 경계와 재지 않는 것
   (cloze 프레임·O로 시작하는 약물명·basic 단위 길이·짧은 정답의 형식 구성)을 고정한다.
3. `studyez_contracts/CLAUDE.md` — bank 계약 한 줄에 새 측정과 검사 위치를 적는다.
4. `docs/changes/2026-11-08-bank-quality-checks/` — 이 기록.

운영 데이터는 읽기만 한다(선을 잡고 결과를 대조하는 SELECT). 쓰기 없음.

## 검사 명령과 성공 조건

| 이름 | 명령 | 성공 조건 |
|---|---|---|
| quality | `python -m pytest tests/quizbank/test_answer_quality.py -q` | 16개 통과 |
| contracts | `python -m pytest tests/contracts -q` | 전부 통과 |
| quizbank | `python -m pytest tests/quizbank -q` | 전부 통과(실물 은행 errors 동치 포함) |
| regression | `python -m pytest tests -q` | 내 변경으로 새로 깨지는 것 없음 |
| server bank | `server/` 에서 `.venv/Scripts/python.exe -m tests bank` | 33개 통과 |
| server route·retention | 같은 자리에서 `-m tests route` · `-m tests retention` | 경로 171개 동일 |
| 구조 | `python scripts/map_numbers.py --check` | 의존 경계 정상 |
| 실물 대조 | 운영 `quiz_bank` 35편과 `root_content` 1편에 새 검사를 직접 돌린다 | spec 의 수용 기준 숫자와 일치 |

## 위험·복원·승인할 범위

- **경고가 많아 묻힐 위험.** 건강한 편에서 편당 중앙 2개가 되도록 선을 p97 에 뒀다.
  첫 판은 basic 에도 단위 길이 선을 대어 건강한 편당 7개가 나왔고, 그 선을 걷었다.
- **오탐 위험.** 극성 판정이 한 글자 O 를 잡아 운영 은행에서 34번 틀렸다. ox 에서만
  O/X 를 극성으로 보도록 좁히고 회귀 검사를 넣었다.
- **문항을 떨어뜨릴 위험.** 측정을 errors 에 넣으면 `validate_dropping` 이 문항을 빼거나
  (문항에 귀속되지 않는 은행 전체 경고라면) 은행을 통째로 막는다. 그래서 warnings 만 쓴다.
- 복원: 코드 변경이 한 파일이라 revert 한 번이면 끝이다. 데이터·운영 설정 변경이 없다.
- 승인 범위: 이 파일들과 검사·기록까지다. 프롬프트 수정, 감염병리1 재출제, master 병합,
  배포는 이 승인에 들어 있지 않다.
