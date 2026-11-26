# 가장 중요한 연결이 답 자리에 — 구현 계획

승인: 사용자 2026-11-26 「권장안대로」(spec 「결정」 네 항목). 범위는 아래 1~4단계의 로컬 구현·검사·Draft PR이다.
Ready·병합·러너 재설치·공개판 보강·운영 요청은 이 승인에 들어 있지 않다.

## 변경 범위·대상 파일·순서

1. **출제 지시문(첫 은행)** — `content/prompts/bank/bankPrompt.md` 1.84 → 1.85
   - §2: 판단·행동도 연결이라는 문장. §2.1에 「가장 무거운 연결을 답 자리에」 예시(합성 주제).
   - §3.2: 족보를 근거로 드는 문항의 답은 족보 정답 선지가 말한 판단(R2).
   - §3.4: 범주·개수·중간 단계가 곧 물어야 할 판단이면 발문에 쓰지 않는다(R4). 묘사를 주고 이름만 답하게 하지 않는다(R5).
   - §4.2: 검수 질문 한 줄(R4).
   - 피부근염에서 어긋난 문항(DM-Q003·017·034·043)은 모두 이 지시문으로 쓴 첫 은행 문항이다.
2. **root-generation/4 단계 지시문** — `content/prompts/learning-links/`
   - `v4/presuppose.md`: 발문이 사실로 준 판단·행동도 상위 연결로 적는다. 증례의 자료와 결론을 가른다(R1).
   - `v4/normalize.md`: 존재 목표 문단에 판단·행동 연결.
   - `v4/add.md`·`v4/fix.md`: 판단 연결의 존재 문항 모양(발문은 상황, 답은 판단), 싣지 않는 것 예 셋(R4), 이름표 방향(R5), `current_exam` 설명(R2).
   - `map-tree/bank-task-v4.md`: `current_exam` 설명(R2).
   - `v4/item-review.md`: 설계 판정의 한 질문과 예 셋(R4), `off_level_exam_years`(R2).
3. **코드**
   - `studyez_contracts/bank/importance.py`: `importance-basis/3`. `question_table(..., carries=, off_level=)`.
     - `off_level`: 문항별로 뺄 `current_exam` 연도. 점수는 뺀 근거로 계산하고 원래 근거와 뺀 연도를 함께 남긴다.
     - `carries`: {줄기 문항: [그 연결을 발문에 준 문항]}. 줄기 등급을 그 문항들의 최고 등급까지 올린다(규칙 `carries`, 사슬은 끝까지 따라간다). `exam_exclusion`은 그대로 Optional.
     - 두 인자가 모두 None이면 지금 /1·/2와 한 글자도 다르지 않다.
   - `studyez_contracts/roots/generation_v4.py`
     - `ANSWER_LEVEL = 'answer-level/1'`.
     - `review_schema`·`check_review_input`: 입력에 `exam_level`이 있을 때만 `off_level_exam_years`를 받는다(그 문항의 `current_exam` 연도 안).
     - `carried_by(brief, bank, coverage_rows, presuppositions)`: 전제 줄의 `recalled_by`, 존재 목표를 통째로 답하는 문항(`pre.whole_answers`).
     - `assemble(..., answer_level=False)`: 켜지면 위 둘을 등급표에 넘긴다. 검증 쪽은 `meta.get('answerLevel')`로 같은 값을 넘긴다.
     - `importance_warnings`: `carriedFloor`, `offLevelExam` 보고.
   - `quizbank/connection_generate_v4.py`: 새 실행의 `fresh`에 `answerLevel`, 검토 입력에 `exam_level`, 조립과 manifest에 전달.
   - 보강·교체 경로(`connection_presuppose.py`·`connection_replace.py`·`connection_dedupe.py`)는 인자를 넘기지 않는다. 공개판 등급은 그대로다.
4. **검사** — `tests/contracts`(importance /3, carried_by, 검토 스키마), `tests/quizbank`(v4 실행 한 벌), 프롬프트 판 검사.
5. **실측 재현(이 PR 밖, 승인 뒤)** — 피부근염을 짧은 경로 사본에서 새 규칙으로 다시 돌려 spec 수용 기준을 센다.
   Codex 호출이 들므로 따로 묻는다.

## 검사 명령과 성공 조건

- `python -m pytest -q tests/contracts tests/quizbank tests/development` 통과.
- `content/prompts/CLAUDE.md`가 정한 `tests/quizbank/test_generate.py`·`test_runtime.py`·`web/tests/bank-prompt-current.test.cjs` 통과.
- 로컬 피부근염 결과(result.json)에 `carried_by`·등급표를 읽기 전용으로 다시 계산해 본다.
  - 존재 문항 12개 중 Optional 1개(Q042)만 남는다.
  - 기존 판을 `answer_level` 없이 검증하면 지금과 같은 문서가 나온다(공개판 호환).
- 실패·미실행·기존 결함은 구분해 적는다.

## 위험·복원·승인할 범위

- **공개판 호환**: 서버는 결과를 다시 조립해 대조한다. 새 계산은 manifest의 `answerLevel`이 있을 때만 돈다. 없는 판은 지금 경로 그대로다.
- **지시문은 새 출제 전부에 적용된다.** 병합하면 API·웹이 배포되고, 러너는 재설치해야 새 지시문을 쓴다. 둘 다 이 계획의 승인 범위 밖이다.
- **Must-Know 수가 는다.** 줄기 문항이 위 문항의 등급을 받는다(피부근염 +2). 비율 경고(34%) 문구는 그대로 두고 올라간 문항을 따로 보고한다.
- **되돌리기**: PR revert. 지시문 판(1.84)과 /2 등급표는 코드에 그대로 남는다.
- **조정**: 객관식 선지 규칙(`mcq/write.md`)은 건드리지 않는다. 「선행 문항 포함」 토글(#228)과는 독립이다.
