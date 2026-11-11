# Main-Quiz 단답·나열 선지 보기 — 설계

## 요구사항과 수용 기준

### 한 장 요약
문항은 그대로 두고, 선지만 판(revision)마다 별도 자료(asset)로 만든다.
게시 뒤 근거 보강(`root_evidence`)과 같은 자리·같은 방식이다.

```
게시 완료 ──▶ 근거 보강(기존) ──▶ 선지 작성(새 단계) ──▶ asset root_choices/<revision>.json
                                                             │
풀이 화면 ◀── 서버가 앞면에 선지를 붙임 ◀──────────────────────┘
  └ 처음엔 숨김 → 「선지 보기」로 펴기 → 고르기 → 답 보기 → 네 버튼 평가
```

이 구조를 고른 이유:
- 계약이 단답·나열의 `options`를 금지한다(`studyez_contracts/bank/validate.py`: 「선택형이 아닌 문항의 options는 비워야 합니다」).
  계약을 풀거나 형식을 객관식으로 바꾸면 커버 판정·회상 단위·중복 판정이 함께 흔들린다.
- 판의 문서를 바꾸지 않으므로 이미 공개된 판에도 덧붙일 수 있고, 학습 기록 승계와 무관하다.
- v4 출제 지시문·`connection_generate_v4.py`·`generation_v4.py`를 건드리지 않아 goal-dedupe와 파일이 겹치지 않는다.

### 선지의 모양
- 단답: 정답 1개 + 오답 3~4개(총 4~5개).
- 나열: 정답 단위 전부 + 오답 2~4개, 총 10개 이하. 정답 단위가 9개 이상이면 선지를 만들지 않는다.
- 오답은 같은 범주에서 실제로 헷갈리는 것이어야 한다. 먼저 같은 강의의 다른 문항 정답·개념 지도의 형제 개념에서 고르고,
  부족할 때만 새로 쓴다.
- 좋은 오답을 만들 수 없는 문항은 건너뛴다(선택적 작성). 건너뛴 이유를 기록한다.
- 위 개수는 제안값이다. 구현 중 실제 문항으로 조정할 수 있다.

### 풀이 화면(`RootSolve`)
- 선지가 있는 단답·나열 문항은 문제 아래에 조용한 버튼 「선지 보기 `C`」를 둔다. 선지가 없으면 버튼도 없다.
- 펴면 선지 목록이 나온다. 단답은 하나, 나열은 여러 개를 고를 수 있다. 고르지 않고 답을 봐도 된다.
- 고른 선지와 「폈음」 상태는 기존 객관식과 같은 방식으로 이 브라우저에 보관한다(새로고침·되돌리기 뒤에도 유지).
- 답을 보면 선지마다 맞게 고름·빠뜨림·잘못 고름을 표시한다(기존 `QuestionBody` 표시 재사용).
- 평가는 지금과 같은 네 버튼이다.
- 단축키(D1 추천안): 스페이스바·Enter는 「답 보기」 그대로, `C`(`event.code === 'KeyC'`, 한글 입력 상태에서도 동작)가 선지를 편다.
  D1을 「다른 길」로 정하면 선지가 있고 아직 안 편 문항에서만 첫 스페이스바가 선지를 편다.
- 타이머: 선지를 펴도 문제 시간은 다시 세지 않는다. 0초가 되면 지금처럼 답을 편다.

### 평가와 기록
- 선지를 편 풀이는 서버에 `choicesShown: true`로 가고 `helped`로 기록된다.
- 현재 네 버튼 평가의 복습 간격은 자기평가(Again·Hard·Good·Easy)만으로 계산되고 `helped`는 기록으로만 남는다
  (`policy.transition`의 self_rating 갈래). 따라서 D2 추천안에서는 복습 간격 계산이 바뀌지 않는다.

### 수용 기준
1. 선지 asset이 없는 판은 화면·API 응답이 지금과 같다.
2. 선지가 있는 단답 문항: 처음에는 선지가 안 보이고, `C` 또는 버튼으로 펴지며, 스페이스바는 답을 편다.
3. 나열 문항: 여러 개를 고를 수 있고, 답을 본 뒤 맞게 고름·빠뜨림·잘못 고름이 표시된다.
4. 선지를 편 풀이의 이벤트에 `helped: true`가 남고, 안 편 풀이는 지금과 같다.
5. asset의 판·문항 지문이 현재 문서와 다르면 그 문항은 선지 없이 나온다(오래된 선지를 붙이지 않는다).
6. 앞면 응답에 정답 선지 표시가 없다(정답 ID는 답을 편 응답에만 있다).
7. 선지 작성 단계가 실패해도 게시된 판과 학습은 그대로다.
8. 코드 검사를 통과하지 못한 문항의 선지는 asset에 들어가지 않는다.

## 책임·입출력 계약·오류 상태

### asset `root_choices` — `root-choices/1`
파일명 `<revision>.json`. 강의의 기존 asset 업로드 경로를 쓴다.

```json
{
  "schema": "root-choices/1",
  "revision": "auto-…",
  "bank_hash": "…",
  "questions": {
    "Q012": {
      "question_hash": "…",
      "choices": [{"id": "A", "text": "…"}, {"id": "B", "text": "…"}],
      "correct_ids": ["B"],
      "wrong_reasons": {"A": "…"}
    }
  },
  "skipped": {"Q013": "같은 범주의 헷갈리는 오답이 없음"}
}
```

- `question_hash`·`bank_hash`는 근거 보강과 같은 계약 함수로 계산한다.
- `wrong_reasons`는 오답마다 왜 틀렸는지 한 줄이다. 검사와 관리자 검토용이며 1차에서는 화면에 내지 않는다.

### 계약 검사 — 새 `studyez_contracts/roots/choices.py`
모델 결과를 문항마다 검사하고, 실패한 문항만 버린다.
- 대상 형식은 basic·list뿐이다.
- 단답: 선지 중 정답과 같은 것이 정확히 하나다(정규화 후 비교).
- 나열: 정답 단위가 모두 선지에 있고, `correct_ids` 수가 정답 단위 수와 같다.
- 오답이 정답·정답 단위·문서의 동의 표현(`equivalences`)과 같지 않다. 선지끼리 중복이 없다.
- 선지 수가 위 범위 안이고, 빈 글이 없고, 오답마다 `wrong_reasons`가 있다.
- 선지 글이 질문 문장에 그대로 들어 있지 않다(문제가 답을 알려 주는 경우 방지).

### 작성 단계 — 새 `quizbank/root_choices.py`, `runner/root_choices.py`
- 러너가 게시 완료·근거 보강 뒤에 하위 프로세스로 실행한다(`runner/connection_generation.py`의 `publish_evidence` 다음 줄).
- 모델 호출은 기존 길 그대로 `studyez_llm.codex`(Codex CLI, 빈 세션)다. API를 직접 부르지 않는다.
- 입력은 판 문서의 글뿐이다: 대상 문항의 질문·정답·정답 단위·해설, 같은 강의의 다른 문항 정답 목록, 개념 지도.
  강의 PDF·족보는 보내지 않는다.
- 40문항씩 묶어 호출한다. 실측 4강의 평균 대상 111문항이면 강의당 약 3회다.
- 지시문은 새 파일 `content/prompts/learning-links/choices/write.md`다. 기존 지시문은 고치지 않는다.
- 묶음 하나가 실패하면 그 묶음만 빠진 asset을 올린다. 재시도는 묶음당 한 번이다.
- 이미 asset이 있고 판·지문이 같으면 다시 만들지 않는다. 기존 검수 상한과 무관한 별도 단계다.

### 서버
- `server/app/models/lectures.py`: `ASSET_KINDS`에 `root_choices` 추가. `Asset.kind`는 `String(24)`이고 DB 제약이 없어 스키마 변경이 아니다.
- 새 `server/app/root_learning/choices.py`: asset 읽기(근거 보강과 같은 캐시 방식), 판·지문 대조, 문항에 붙이기.
- 앞면(`content.front`의 결과에 덧붙임): 단답·나열에 `recall_choices: [{id, text}]`. 순서는 문항 ID로 정해지는 고정 섞기다.
  기존 `options`는 비운 채로 둔다 — 옛 화면이 `options`로 「선지 있음」을 판단하지 않게 한다.
- 답면: `recall_correct_ids`.
- `prior_exposure`: `choicesShown`이 참이고 그 문항에 `recall_choices`가 있으면 `helped`로 본다.
- 오류 상태: asset이 없거나 깨졌거나 판이 다르면 선지 없이 응답한다. 풀이를 막지 않는다.

### 화면
- `web/src/bank/RootSolve.tsx`: 버튼·단축키·고르기·보관, `reveal`에 `choicesShown`.
- `web/src/bank/BankQuestion.tsx`: `QuestionBody`가 단답·나열에서 `recall_choices`를 선지 목록으로 그린다.
- `web/src/notices/GuidePage.tsx`: Main-Quiz 안내에 한 줄.

## 호환성과 데이터 보존
- 문항·판·학습 기록·DB 스키마를 바꾸지 않는다. 은행 교체·공용 문항 수정이 아니므로 `bank_retention` 대상이 아니다.
- 선지를 편 풀이의 이벤트에만 `helped: true`가 새로 생긴다. 과거 이벤트는 건드리지 않는다.
- 옛 화면(배포 전 캐시)은 `recall_choices`를 모르므로 지금과 똑같이 보인다.
- asset을 지우면 기능이 꺼진다. 판과 학습은 그대로다.
- 옛 Quiz Bank(`BankSolve`)·Pre-Quiz·`option_pools`는 바꾸지 않는다.
