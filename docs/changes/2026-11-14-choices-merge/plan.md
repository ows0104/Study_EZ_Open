# 선지 보기·객관식 모드 선지 합치기 — 구현 계획

spec의 열린 질문 6개는 2026-11-14에 사용자가 답했다(spec 「사용자 결정」).
구현은 (1) 사용자의 구현 시작 요청과 (2) 대시보드의 「복습 퀴즈 객관식 모드」(HungryPotato01)와 파일 조정이 끝난 뒤 시작한다.

## 변경 범위·대상 파일·순서

| 순서 | 영역 | 파일 | 내용 |
|---|---|---|---|
| 1 | 계약 | `studyez_contracts/roots/mcq.py`, `tests/contracts/` | `root-mcq/2`, 출처 넷, 표기 갈래·길이·단정 표현 검사, 오답 수 고정 없음(보이는 4~5), cloze `{답}` 빈칸, 풀이 차례로 오답 고르기(순수 함수) |
| 2 | 지시문 | `content/prompts/learning-links/mcq/write.md`·`review.md`, 새 `jokbo.md` | 출처 넷·매력·표기 맞춤, 독립 검토, 족보 선지 읽기 |
| 3 | 생성 | `quizbank/root_mcq.py`, `tests/quizbank/` | 과목 족보 풀 단계(PDF sha 캐시, 다른 강의 족보 포함), 오답 수 고정 없음, 단서 검사 탈락 → 둘째 회차 |
| 4 | 연결 | `runner/root_mcq.py`, `runner/connection_generation.py`, `tests/runner/` | packet 족보 PDF 전달, 게시 직후 `root_mcq.publish`로 교체, v1 로컬 사본 보존 |
| 5 | 서버 | `server/app/root_learning/mcq.py`, `server/app/routes/root_learning.py`, `server/tests/` | v1·v2 읽기, 풀이 차례, 답면 `mcqWrongNotes` |
| 6 | 화면 | `web/src/bank/quizMode.ts`, `RootSolve.tsx`, `BankQuestion.tsx`, `web/src/types/bank.ts`, `web/tests/` | 주관식 `V`가 `mcq_choices` 사용, 답면 「왜 틀렸나」 |
| 7 | 문서 | `docs/map.md`, `quizbank/CLAUDE.md`, `runner/CLAUDE.md`, `docs/artifact-contract.md`, README 「한 장 그림」(게시 뒤 단계가 바뀌면) | |
| 8 | 시범 | 261110_03(리케치아), 261102_02(병인론), 261112_02(족보 직접 연결 22문항) `--no-upload` | 비율·표기 갈래·족보 출처 수·의학 검토 탈락을 세고 표본 30문항을 사람이 읽는다 |
| 9 | 배포 | master 병합 → API·웹 자동 배포 → 러너 재설치 | |
| 10 | 재생성 | 게시된 감염과 면역 27강의 → 업로드 | |

건드리지 않는 파일: v4 출제 지시문·`connection_generate_v4.py`, `web/src/bank/BankSolve.tsx`, `server/app/root_learning/choices.py`(읽기만 남김).

## 검사 명령과 성공 조건
- `python -m pytest tests/contracts tests/quizbank tests/runner`
  - 새 검사: 표기 갈래·길이·단정 표현 거절, 오답 1개만 남은 문항도 붙음, cloze `{답}` 대상, 풀이 차례별 오답 고르기(같은 차례 같음·다음 차례 다름·정답 전부 포함), v1 사본 보존, 게시 직후 호출 교체
- `server/`에서 `PYTHONPATH=.. .venv/Scripts/python.exe -m tests root`·`mcq`
  - 앞면에 정답·이유·출처 없음, 답면에 보인 오답만, v1·`root_choices` 판은 지금과 같음
- `web/`: `npm run typecheck`, `npm run build`, Main-Quiz 화면 검사(주관식 `V` → 같은 선지, 답면 한 줄)
- 로컬 미리보기는 격리된 로컬 DB·저장소로만 한다
- 시범 성공 조건: 표기 갈래가 갈리는 문항 0, 선지 붙은 비율 ≥ 지금(같은 강의의 v1), 표본 30문항에 「정답으로도 성립하는 오답」 0

## 위험·복원·승인할 범위
위험:
- **시험(2026-11-20) 전 시간.** 구현·배포·재생성이 늦으면 지금 올라간 v1을 그대로 쓴다. 재생성은 학생이 공부 중인 판의 선지를 바꾼다.
- **풀이 차례 계산.** 앞면·답면이 다른 차례를 쓰면 답면 정답 ID가 맞지 않는다. 계약 함수 하나로 묶고 검사한다.
- **족보 읽기.** 쪽 이미지에서 보기·정답을 잘못 읽을 수 있다. 의학 검토와 시범 읽기로 거른다.
- **비용.** 오답 풀이 커지고 족보 단계가 늘어 강의당 호출·시간이 지금(27강의 71분, 3강의씩)보다 는다. 시범에서 잰다.
- **기본 실행 시간.** 게시 직후 단계가 길어져 러너의 한 편 시간이 는다.

복원:
- 화면·서버는 커밋 되돌리기. DB 변경 없음.
- 재생성 뒤 문제가 있으면 보존한 `mcq/v1-<revision>.json`을 `--upload-only`로 되올린다.

승인할 범위:
- 지금: 이 설계 문서(intent·spec·plan)만. 코드 변경 없음.
- 따로 승인: 구현 시작(1~7), 8번 시범의 모델 호출, 9번 병합·러너 재설치, 10번 재생성·업로드(학생에게 보이는 선지가 바뀜).
