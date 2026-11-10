# root-generation/3: 판정 값이 강의를 멈추지 않게 — Implementation Plan

[spec.md](spec.md)의 P7·R5a′·R5′·R6′·R7·R8을 한 PR로 넣는다. 구현 승인은 사용자 2026-11-10 요청(「근본적인 구조를 진단한 후 일반적으로 작동하도록 … 네 주관대로 해줘」)이다.

## 변경 파일과 순서

| 순서 | 파일 | 내용 |
|---|---|---|
| 1 | `studyez_contracts/roots/generation_v3.py` | 충돌별 임상 정리 계약, 의학 검토 입력 나누기, `readiness`, 지도 확인 미수행, `validate_result` 새 칸 |
| 1 | `studyez_contracts/roots/generation_v2.py` | `medical_input`의 정규식에 이름(`HISTORY_MARKERS`)만 붙임. 동작 같음 |
| 2 | `quizbank/connection_generate_v3.py` | 임상 정리 흐름, 조립을 의학 검토 앞으로, 과제 0개 멈춤, 의학 묶음의 빠진 판정, 옛 단계 이름 보관, 경로 길이 |
| 3 | `runner/root_native_json.py` | `v3-context` 단계 연결, `garbled` 수신 검사, 파일 쓰기 지시 |
| 3 | `content/prompts/learning-links/v3/context.md` | 새 프롬프트. `PROVENANCE.md`에 출처를 적는다 |
| 4 | `tests/quizbank/test_root_generation_v3.py` 등 | 아래 검사 |
| 5 | `quizbank/CLAUDE.md`, root-generation/3 spec의 R5a | 안내 갱신 |

## 검사

- `tests/quizbank/test_root_generation_v3.py`
  - 임상 정리: 보완 한 번, 두 번 다 일치가 아니어도 결과가 나옴(과제 같음, 사실은 의학 검토에 안 감), 문항 글 이력, 미수행 재실행
  - 지도 확인 미수행 재실행, 과제 0개는 의학 검토 전에 이유와 함께 멈춤
  - 의학 검토가 빠뜨린 판정, 검수 이력 표현이 있는 문항
  - 옛 `context-0` 기록이 있는 실행의 이어 하기
  - **임의 판정 300가지**(`test_any_judgment_value_reaches_a_result_or_a_named_stop`): 커버·지도 확인·문항 검토·선행·임상 정리·의학 판정을 형식 안에서 무작위로 바꾼다. 결과가 소비자 검증을 통과하거나, 이름 붙은 두 이유로만 멈춰야 한다.
- `tests/contracts/test_generation_v3.py`, `tests/runner/test_root_front_v3.py`, `tests/runner/test_root_native_json.py`(깨진 글자)
- 전체: `python -m pytest tests`, 서버 `python -m tests`(계약을 쓰는 검사)
- 실제 기록 사본 재생(저장소 밖 임시 폴더, 모델만 바꿔 끼움): 러너 `_generate` → 옛 결과 보관 → 생성기 진입점 → 수신 검사·영수증 → `validate_all` → 결과 검증 → 가짜 업로드
  - 가짜 모델 세 가지: 전부 일치 / 오염 뒤 보완으로 일치 / 보완 뒤에도 오염
  - 실제 모델 한 번: 새 임상 정리와 의학 검토

## 한계

- 임의 판정 검사는 작은 합성 강의에서 돈다. 형식이 맞는 판정 값의 조합은 덮지만, 모델이 형식 밖 출력을 고집하는 경우는 단계 실패(이어 하기 대상)로 남는다.
- 실제 모델의 판정이 얼마나 흔들리는지는 재지 않았다. 이제 흔들려도 그 기록의 사실 전달만 달라진다.
- 끝까지 돈 실제 강의는 261102_02 하나다.

## 복원

- 코드: PR revert. /2와 서버 DB는 건드리지 않았다.
- 실행 폴더: 이어 하기가 옮긴 단계 기록은 `.resume-<k>/`에 그대로 있다.

## 배포 뒤 할 일

- 러너 설치본을 새 master로 다시 깐다(메모리 「러너 새 코드 반영 절차」).
- 관리자가 261102_02를 이유와 함께 이어서 만든다. 새로 부르는 것은 `v3-context-0`과 의학 검토다.
