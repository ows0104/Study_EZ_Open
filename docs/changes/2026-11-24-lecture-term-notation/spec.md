# Spec: 의학용어는 강의록 표기대로, 필요하면 병기

## 의도

사용자 지시(2026-11-24): 「답과 문제의 의학용어가 너무 한글화되어서 가끔 문제가 어려워.
강의록의 표기를 따르고 필요한 경우 병기하면 어떨까?」 → 제안한 규칙 ①~④에 「Yes, 진행」.

## 진단(로컬 runs/_root-generation, 운영 쓰기 없음)

게시된 판(`generation/result.json`의 bank_snapshot)의 답과 같은 판의 강의록 글(`generation/material/*.md`)을 대조했다.
강의록은 영어인데 답이 한글 번역어인 예:

| 강의(판) | 강의록 | 답 |
|---|---|---|
| 레지오넬라·리스테리아·바실루스 (6d8bd70b) | macrophage | 대식세포 |
| 레오·코로나·노로 (d51b2e83) | ciliated epithelial cells | 섬모상피세포 |
| 포도알균 (b1fe4257) | polymorphonuclear, nonmotile | 다형핵백혈구, 비운동성 |
| 필로·분야 (caa02077) | segmented, single strand, polymerase | 분절된 음성 단일가닥, 중합효소 |
| 척추 관절염 (dd3b083b) | AV block | 3도 방실차단 |
| 랍도·지발 (4ccb0990) | peripheral nerve, aerosol | 말초신경, 에어로졸 |

강의록이 한글인 곳(면역약리학 51637d39의 잠복결핵·폐포자충 폐렴, 척추 관절염 33쪽의 굴곡건·건막)은 강의 표기대로 나갔다.
따라서 문제는 「강의록이 영어인데 모델이 옮겨 쓴다」이다.

원인: Main-Quiz 첫 출제(`parallel/bank.md` + `map-tree/bank-task-v4.md`)·보강(`v4/add.md`)·고치기(`v4/fix.md`)·
검토(`v4/item-review.md`)에는 공용 출제 원칙(`bankPrompt.md` §2~§3, §4.2, `quizbank/generate.py`
`item_quality_guidance`)이 덧붙는다(`runner/root_front.py`, `runner/root_native_json.py`). 거기 표기 규칙은 §3.4의 한 줄뿐이다.

> 일반 문장은 자연스러운 한국어로 쓰고 원본의 전문 용어·약어·영어 표기는 유지한다. 필요하면 한국어 뜻을 병기한다.

「자연스러운 한국어」가 앞에 오고 무엇이 전문 용어인지는 정하지 않아서, `peripheral nerve`·`segmented` 같은 말이
일반 문장으로 옮겨졌다. 예습 퀴즈 쪽 `quizgen/prompts/domains/medical_ko.md`에는 같은 문제를 다룬 순서 규칙이 이미 있다.

## R1 §3.4 표기 줄을 순서 규칙으로 (bankPrompt 1.84)

`medical_ko.md`의 규칙을 공용 출제 원칙에 옮긴다. 발문·정답·채점 단위·explanation 모두에 적용한다.

1. 강의록(슬라이드·필기)이 그 개념을 부르는 말을 그대로 쓴다. 번역어로 바꾸지 않는다.
2. 강의록에 표기가 없으면 영어 의학용어를 쓴다. 한글 번역어를 지어내지 않는다.
3. 학생이 처음 만날 만한 어려운 용어는 괄호로 병기한다. 앞은 강의 표기다. 애매하면 병기한다.
4. 한 강의 안에서는 같은 개념을 한 표기·같은 병기 꼴로 통일한다. 기존 문항을 고치거나 더할 때도 그 표기를 따른다.

조사·서술 같은 일반 문장은 그대로 자연스러운 한국어다. 동의어·약어·다른 표기를 정답으로 인정하는 채점 규칙(§3.4)도 그대로다.

## 범위

- 바뀌는 파일은 `content/prompts/bank/bankPrompt.md` 하나다(+ 빌드 산출 `web/public/bank-prompt.json`).
  이 문단이 웹 Quiz Bank 출제문과 Main-Quiz 첫 출제·보강·고치기·검토에 모두 붙는다.
- 선지(`learning-links/mcq/write.md`)는 「정답과 같은 언어·같은 병기 꼴」 규칙이 이미 있어 새 답 표기를 따라간다.
- 새 출제·보강·고치기부터 적용된다. 이미 게시된 문항은 바꾸지 않는다(문항·ID·학습 기록 보존).
  게시된 문항을 다시 쓸지는 별도 결정이다.
- 코드·스키마·DB 변경 없음.
