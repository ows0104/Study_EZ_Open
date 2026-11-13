# 복습 퀴즈 객관식 모드 — 구현 계획

## 변경 범위·대상 파일·순서
| 순서 | 영역 | 파일 |
|---|---|---|
| 1 | 계약 | 새 `studyez_contracts/roots/mcq.py` |
| 2 | 출제 | 새 `quizbank/root_mcq.py`, `content/prompts/learning-links/mcq/write.md`·`review.md`, `tests/quizbank/test_root_mcq.py` |
| 3 | 연결 | 새 `runner/root_mcq.py`(수동 명령, 게시 경로 불변 — 러너 재설치 불필요) |
| 4 | 서버 | `server/app/models/lectures.py`(ASSET_KINDS), 새 `server/app/root_learning/mcq.py`, `routes/root_learning.py`, `server/tests/test_main_quiz_mcq_choices.py`, 화면 확인용 `serve_main_quiz_mcq_fixture.py` |
| 5 | 화면 | 새 `web/src/bank/quizMode.ts`, `RootToday.tsx`(토글), `RootSolve.tsx`, `BankQuestion.tsx`, `types/bank.ts`, `main-quiz.css`, `notices/GuidePage.tsx` |
| 6 | 생성 | 러너 PC 세션(fork): 시범 1~2강의 `--no-upload` → 감염과 면역 전체 병렬 → 배포 뒤 `--upload-only` |

## 검사 명령과 성공 조건
- `python -m pytest tests/contracts tests/quizbank tests/runner`
- `server/`: `.venv/Scripts/python.exe -m tests main_quiz`, `route_contract`
- `web/`: `npm run typecheck`, `npm run build`, 로컬 fixture(격리 sqlite)로 단답·나열·OX 객관식 풀이를 브라우저에서 확인

## 위험·복원·승인할 범위
- 오답이 사실은 정답일 위험: 독립 의학 검토로 줄이고, 학생 제보 경로가 있다.
- 시간: 강의당 묶음 3~6개 × (작성+검토). 실패 묶음·문항은 빼고 진행하고 아침에 보고(사용자 지시).
- 복원: 병합 커밋 revert, asset 삭제. 판·학습 기록은 그대로.
- 승인: 사용자의 야간 요청이 구현·PR·병합·배포·선지 생성·업로드까지 포함한다.
