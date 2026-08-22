# 과제 ② — 승인된 학습 목표를 카드로 만든다

승인된 학습 목표가 `{plan_in}`에 있다. 이것을 입력으로 카드를 만든다.

## 원칙

- 각 회수 목표는 **최소 한 장**의 카드로 덮는다. 목표 하나에 카드 여러 장이어도 된다.
- 목표에 없던 것을 새로 카드화하지 마라. 꼭 필요하면 만들되 왜 계획에 없었는지 `explanation`에 적는다.
- 승인 과정에서 사람이 목표를 추가·삭제했을 수 있다. **파일에 있는 것이 정본이다.**

## 형식 고르기

| 상황 | 형식 |
|---|---|
| 정의·기전·비교를 묻는다 | `basic` |
| 한 문장 안에서 여러 항목을 각각 회수시킨다 | `cloze` |
| 흔한 오해를 정면으로 친다 (기출 오답 선지에서 뽑은 것 포함) | `ox` |
| 사진·조직학·모식도 자체를 알아봐야 한다 | `image_basic` |
| 그림 속 특정 구조의 이름·위치를 회수시킨다 | `image_occlusion` |

텍스트로 바꾸면 위치·형태 정보가 사라지는 것만 이미지 카드로 낸다.
글로 충분한 내용을 그림에 얹지 마라.

## cloze

**빈칸 하나가 카드 하나다.** 번호를 다섯 개로 가르면 Anki 는 카드를 다섯 장 만들고,
그 각각은 **나머지 넷을 앞면에 인쇄한 채** 자기 것 하나만 가린다. 이걸 모르고 뚫으면
답의 대부분이 앞면에 적힌 카드가 나온다.

```
q   Inflammation is a complex reaction to {{c1::injurious agents}} such as microbes
    and damaged, usually {{c2::necrotic}}, cells that consists of
    {{c3::vascular responses}}, {{c4::migration and activation of leukocytes}},
    and {{c5::systemic reactions}}.

c1 카드의 앞면 →
    Inflammation is a complex reaction to [...] such as microbes and damaged,
    usually necrotic, cells that consists of vascular responses, migration and
    activation of leukocytes, and systemic reactions.
```

물어 놓은 것이 `injurious agents` 하나이고 나머지는 다 적혀 있다. 실제로 나온 카드이고
관리자가 **못 쓴다고 판정했다.**

**한 축에 나란히 놓인 항목은 같은 번호로 함께 가려라.** 한 번호는 함께 열리고 함께
닫히므로 한 장이 그 축 전체를 묻는다. 번호를 가르는 것은 **축이 서로 다를 때**뿐이다.

```
좋음  ... consists of {{c1::vascular responses}}, {{c1::migration and activation
      of leukocytes}}, and {{c1::systemic reactions}}
      → 「염증이 무엇으로 이루어지는가」 를 한 장으로 묻는다
```

**빈칸마다 왜 그 자리를 가렸는지 말할 수 있어야 한다.** 못 하겠으면 그 빈칸을 지우거나
카드를 `basic` 으로 바꿔라 — 문장이 흐르는 대로 적당히 뚫는 것이 아니다. 위 예에서
`injurious agents` 가 그 자리였다.

**정의문을 통째로 옮겨 놓고 여기저기 뚫지 마라.** 정의를 묻고 싶으면 `basic` 이다.
빈칸 문장이 길면 검사기가 `cloze_sentence_too_long` 으로 표시한다 — 못 쓴다는 뜻은
아니지만, 길어야 할 이유가 그 문장에 있어야 한다.

**가린 말이 같은 문장 다른 자리에 맨몸으로 또 나오면 안 된다.** 앞면에서 그 자리만
가려지므로 나머지 한 자리가 답을 그대로 읽어 준다. 같은 말이 두 번 필요하면
**두 자리 모두 같은 번호로 가린다.**

```
나쁨  ... {{c1::EGFR}} 변이이고, {{c3::Iressa}}는 EGFR tyrosine kinase inhibitor다
      → c1 을 물을 때 뒤쪽 EGFR 이 답을 흘린다
좋음  ... {{c1::EGFR}} 변이이고, {{c3::Iressa}}는 {{c1::EGFR}} tyrosine kinase inhibitor다
```

## 이미지 카드

사이드카가 후보를 미리 뽑아 두었다. **id를 그대로 인용해라. 좌표를 직접 만들지 마라.**

- `image_basic` — `media.figure_id`에 `fig_pNN_MM`을 넣는다. 카드의 `slide_no`는 그 그림이 있는 슬라이드여야 한다.
- `image_occlusion` — `media.figure_id`와 `media.occlusion_ids`(`occ_pNN_MM`)를 넣는다.
  가려진 라벨이 답이다. 그 라벨 텍스트를 `q`에 노출하지 마라.

후보 중에는 구조 라벨이 아닌 것도 섞여 있다(필기자 사담, 교수 잡담, 긴 설명문).
회수 가치가 있는 것만 고르고 나머지는 무시해라. `label`이 `null`인 후보는
필기자가 영역만 표시한 것이니, 그 안에 무엇이 있는지 그림을 보고 직접 판단해라.

## 기출 카드

기출 조각의 문항은 두 갈래로 쓴다.

1. **`source_type=jokbo` 카드** — 문항 자체가 회수 가치가 있을 때. `jokbo_ref`에 연도·번호를 단다.
   원문을 그대로 옮기지 말고 자족적인 질문으로 다시 쓴다.
   `exam_hit`은 부여하지 않는다.
2. **강의록 카드의 `exam_hit` 근거** — 같은 회수 목표를 물은 기출이 있으면
   `exam_hit=true`와 `jokbo_ref`(`role: "exam_hit_evidence"`)를 단다.

오답 선지 채굴과 이의제기 활용은 출제 철학을 따른다.

## 분량

목표 수를 맞추려 하지 마라. 회수 목표가 요구하는 만큼만 낸다.
좋은 후보를 놓치는 것보다는 조금 넉넉한 편이 낫다 —
저가치·중복 카드는 뒤 단계에서 근거를 남기고 걸러진다.

## 출력

`generate.schema.json`의 `cards` 배열만 채워 아래 경로에 쓴다.
`learning_plan`은 **다시 싣지 마라.** 코드가 승인본을 직접 읽는다.
다른 말은 덧붙이지 않는다.

    {cards_out}
