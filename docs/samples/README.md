# 표본

서버·웹이 붙을 실제 산출물이다. 파이프라인을 돌리지 않고도 화면을 만들 수 있게
고정해 둔다. 모양이 궁금하면 `../artifact-contract.md`를 함께 보라.

| 파일 | 무엇 | 어디서 나왔나 |
|---|---|---|
| `pre_items.sample.json` | **Pre-Quiz 웹 풀이 화면이 읽는 것.** 17문항 | 병리학 `250820_02` 멘델법칙을 따르지 않는 유전자 질환 |
| `run.meta.sample.json` | 덱 하나의 요약. 관리자 화면이 "배포해도 되는가"를 판단하는 값 | 병리학 `260812_01` 병리학 소개 (80장) |

## `pre_items.sample.json`에서 놓치기 쉬운 것

- `qtype`이 셋이다 — `mcq`(`choices` 5개, `answer`는 1-based 인덱스 문자열),
  `short`(`choices` null, `answer`는 텍스트), `ox`(`answer`는 `"O"`/`"X"`)
- **`stem`의 `**강조**`를 렌더링하라.** 부정형 발문을 놓치지 말라고 넣은 것이라
  지우면 문항의 뜻이 바뀐다
- `short`의 채점은 문자열 완전일치가 아니다. `explanation` 첫 줄에 허용 표기가
  적혀 있다 (예: "Leber hereditary optic neuropathy / LHON / Leber 유전성
  시신경병증 어느 표기든 정답이다")
- `slide_no`로 근거 슬라이드를 띄우려면 `media/`도 함께 올라가야 한다

## `run.meta.sample.json`에서 볼 것

- `review_flagged`가 0이 아니면 **사람이 카드 뒷면 경고 박스를 확인해야 한다.**
  족보 정답이 검토 결과와 다른 카드가 있다는 뜻이다
- `slides_unused`는 카드가 하나도 없는 슬라이드다. 많으면 생성이 얕았다는 신호다
- `lecture_id` 필드 이름은 역사적인 것이고 값은 `run_id`다

## 갱신

파이프라인이 바뀌어 모양이 달라지면 여기도 같이 갱신한다. 계약이 움직이면
`../artifact-contract.md`를 먼저 고치고 그다음 표본을 바꾼다.
