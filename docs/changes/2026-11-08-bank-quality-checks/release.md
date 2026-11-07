# Measure recall load and structural answer cues in the bank checker — 배포 준비

## 코드 리뷰·검증 결과

| 검사 | 결과 |
|---|---|
| `pytest tests/quizbank/test_answer_quality.py` | 16개 통과 |
| `pytest tests/contracts` (기록: contracts, exit 0) | 전부 통과 |
| `pytest tests/quizbank` (기록: quizbank, exit 0) | 전부 통과 — 실물 은행 errors 동치 포함 |
| `pytest tests` (기록: regression, **exit 1**) | 2,098 통과 · 3 skip · **1 실패** |
| `server/` `-m tests bank` | 33개 전부 통과 |
| `server/` `-m tests route` | 경로 171개 동일 |
| `server/` `-m tests retention` | 통과 |
| `scripts/map_numbers.py --check` | 의존 경계 정상 |

### 그 1 실패
`tests/runner/test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`
— PowerShell 바로가기 설치기의 `PathNotFound`. 이 변경과 무관하다.
`origin/master`(485c6ac3)만 꺼낸 임시 worktree에서 같은 테스트를 돌려 **같은 자리에서 같은
이유로 실패**하는 것을 확인했다(12 통과 / 1 실패). **고치지 않았다** — 별개 문제다.

### 실물 대조 (운영 DB 읽기 전용)
- 새 Main-Quiz 1편(감염과 면역 `261104_02` `main-quiz-reviewed-6143c8c89ad64d9c`, 98문항):
  errors 0 · warnings 36 — 예/아니오 축 6(Q004·Q079·Q080·Q107·Q109·Q084),
  회상 부담 25, 단정어×부정 3(Q003·Q079·Q080), 정답 쏠림 1, 형식 쏠림 1.
  관리자가 든 두 문항이 이름으로 나온다.
- 운영 `quiz_bank` 35편 3,103문항: 새 경고 합계 62(편당 중앙 2 · 최대 10), errors 증가 0,
  예/아니오 축 0편, 형식 쏠림 0편, 정답 쏠림 5편(OX 정답이 전부 X인 약리 편).
- 첫 판에서 두 번 틀렸고 둘 다 고쳐 회귀 검사로 고정했다 — ① 한 글자 `O` 를 극성으로 보아
  `Olaparib`·`O₂`·`OCT1` 등 34건 오탐, ② basic 에도 단위 길이 선을 대어 건강한 편당 7개 경고.

## 배포 대상 버전·순서·데이터 변경

배포 대상 없음. 순수 Python 계약 모듈과 검사·기록만 바뀐다.
- 서버·웹 코드 변경 0 — API 경로 171개 동일, 웹 자산 미변경.
- DB 스키마·운영 데이터 변경 0. 저장된 `quiz_bank.validation`·`root_content` 는 그대로다.
  새 경고는 **다시 검증하는 경로에서만** 생긴다.
- 프롬프트 변경 0. 정본 `bankPrompt.md` 와 `content/prompts/learning-links/*` 는 손대지 않았다.

새 경고가 흐르는 자리(코드 변경 없이 기존 배선):
`validate_bank` → `connection_generate_v2.py` · `root_plan_repair.py` · `root_chunked_review.py`
의 `validation` → repair 단계 입력, 그리고 `root_generation.py` 의 `issues` ·
`root_learning.py` 의 `reviewIssues`.

## 배포 후 확인·롤백·필요한 사람 승인

- **필요한 승인**: master 병합(=프론트 자동 배포 유발)은 사용자 승인 대기. API 는
  `deploy.ps1` 을 손으로 돌려야 하지만 이 변경에는 서버 재배포가 필요 없다.
- 병합 뒤 확인할 것: 다음 Main-Quiz 생성·검수 한 편에서 새 경고가 실제로 repair 입력과
  관리자 issues 에 나타나는지, 그리고 그 판의 cloze·객관식·답 길이가 달라지는지.
  **측정은 작성자를 바꾸지 않는다** — 달라지지 않으면 프롬프트 쪽(진단 §5의 2·3번)이 남은 일이다.
- 롤백: 한 파일 revert. 데이터 복원 필요 없음.
- 남은 일(이 작업 범위 밖): 웹 Quiz Bank 관리자 목록은 `errorCount` 만 내보내 새 경고가
  목록 숫자로 보이지 않는다. 감염병리1 재출제도 범위 밖이다.
