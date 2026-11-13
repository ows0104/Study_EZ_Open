# 복습 퀴즈 객관식 모드 — 설계

## 요구사항과 수용 기준
1. 진입 화면 시작 카드에 「주관식 | 객관식」, 풀이 화면 머리에 「객관식」 스위치. 같은 저장값(`studyez:main-quiz-mode`)을 쓴다.
2. 객관식 모드의 선지 우선순위: 문항 자체 선지(mcq·multi_select) → `mcq_choices`(객관식 모드 asset) → OX는 O·X → 단답·나열 `recall_choices`. 없으면 그 문항은 주관식.
3. 객관식 모드는 모든 선지를 다중선택으로 받고 「하나를/모두 고르세요」를 내지 않는다. `1`~`9`로 고르고 Space로 확인. 답면에서 맞게 고름·빠뜨림·잘못 고름 표시.
4. 객관식 모드 풀이는 주관식과 같은 기록이다: 덧붙인 선지로 푼 것은 `helped`가 아니다(회상 가능·학습률에 그대로 들어간다). 문항 자체 선지는 주관식 모드와 같은 규칙.
5. asset이 없거나 판·문항 지문이 다르면 선지 없이 지금과 같다. 앞면에 정답 ID·오답 근거가 없다.

## 책임·입출력 계약·오류 상태
- 계약 `studyez_contracts/roots/mcq.py`(`root-mcq/1`): 대상 basic·list·cloze·sequence. 정답 선지는 코드가 만든다.
  cloze 빈칸 여럿·sequence는 칸을 이은 조합(` / `, ` → `) 하나가 정답이고 오답도 같은 칸 수의 조합. 오답마다 `kind`(block·subtle)·`basis`·`why_wrong` 필수.
  오답 수: basic·cloze·sequence 3~4, list 2~4(정답 단위 12개까지), 선지 16개 이하.
- 생성기 `quizbank/root_mcq.py`: 40문항 묶음 작성(`content/prompts/learning-links/mcq/write.md`) → 독립 의학 검토(`review.md`, 작성 쪽 근거를 주지 않음) → 계약 검사.
  검토 뒤 모자라거나 건너뛴·실패한 문항은 뺀 오답과 이유를 주고 둘째 회차 한 번. 블록 재료는 같은 과목 다른 강의 판의 짧은 정답(`block-pool/1`)과 선택적 `--sheet`.
- 러너 명령 `runner/root_mcq.py`: 판을 게시한 PC에서 `--all-published --subject <과목>`, `--no-upload`·`--upload-only`·`--missing`. 결과 `<실행>/mcq/`, 올리면 `mcq/uploaded.json`.
- 서버 `server/app/root_learning/mcq.py`: asset 종류 `root_mcq`(`ASSET_KINDS`), 앞면 `mcq_choices`, 답면 `mcqCorrectIds`. DB 스키마 변경 없음.

## 호환성과 데이터 보존
문항·판·학습 기록·DB 스키마를 바꾸지 않는다. 판 교체가 아니므로 bank_retention 대상이 아니다.
옛 화면은 `mcq_choices`를 모른다. asset을 지우면 객관식 모드에서 그 강의 문항이 주관식으로 돌아간다.
