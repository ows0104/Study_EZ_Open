# Spec: Main-Quiz 앞 단계에도 의학용어 강의록 표기 규칙

## 의도

사용자(2026-11-26): 피부근염(261124_02) Main-Quiz 문항

> Gottron's papule의 특징을 채우시오. 병변 형태: {인설성 홍반성 구진} / 주된 분포: {손등 관절 돌출부, 팔꿈치와 무릎의 신전면}

을 두고 「이런건 왜 안 고쳐졌지? 다 번역이 되버렸어」라고 물었다. 원인을 설명하자 「게시된 문항은 놔두고, 앞으로
출제될거가 어떻게 될지 알려줘」라고 했고, 이어서 「넣어 줘」라고 했다.

## 진단 (로컬 runs/_root-generation/aadee987…, 운영 쓰기 없음)

- 강의록 9쪽 원문: `Gottron's sign/papules: scaly and erythematous papules over the nuckles, knees, and elbows`.
- 이 판은 #245(bankPrompt 1.84, 11-24 14:02 병합)가 나온 뒤인 11-24 19:49에 출제됐다. 출제 단계(v4-add-0)의
  Codex 세션 기록에는 「의학용어 표기는 이 순서로…」 규칙이 들어 있다.
- 한글은 그보다 앞에서 처음 나왔다. 개념 지도(`front/map/concept-map.json` C015, 19:54)에
  「손등 관절, 팔꿈치·무릎 신전면의 인설성 홍반성 구진」, 출제포인트(P015)에 「손등 관절 돌출부(knuckles)… 인설성 홍반성 구진」으로 적혔다.
  두 단계의 task.md에는 표기 규칙이 없다(`runner/root_front.py` ASSET4: `map-extract.md`, `point-extract-v4.md`).
- 출제 단계는 규칙과 슬라이드 그림을 받고도 지도·포인트의 한글 문장을 그대로 답으로 썼다.
  예습 퀴즈 정책(`quizgen/prompts/domains/medical_ko.md`)이 경고하는 실패와 같다:
  계획이 번역어를 한 번 적으면 카드 단계가 그 말을 옮겨 적는다.

## R1 개념 지도·출제포인트 지시문에 같은 순서 규칙

`map-extract.md`과 `point-extract-v4.md`의 「## 출력」 앞에 「## 의학용어 표기」를 넣는다. 내용은 bankPrompt 1.84 §3.4의 ①~④와 같다:
강의 표기 그대로 → 없으면 영어(번역어를 짓지 않음) → 어려운 말은 괄호 병기 → 한 강의 안에서 한 표기로 통일.
「뒤 단계가 이 문장을 그대로 옮긴다」는 이유도 함께 적는다.

포인트 수선(point-repair)은 task를 `point-extract-v4.md` + `map-tree/point-repair-v4.md`로 만들기 때문에 같은 규칙을 받는다.
포인트 감사(audit)는 포인트를 쓰지 않으므로 손대지 않는다. 옛 판(`point-extract-v3.md`, `parallel/*`)도 손대지 않는다.

## 범위

- 지시문 두 파일만 바뀐다. 코드·스키마·DB 변경은 없다.
- 새 출제부터 적용된다. 러너가 새 지시문을 쓰려면 병합 뒤 `.runtime` 재설치가 필요하다.
- 게시된 문항은 바꾸지 않는다(사용자 「게시된 문항은 놔두고」).
- 고치기·검토 단계에 표기 검사를 더하는 일은 이번 범위가 아니다.

## 확인

- `tests/contracts/test_concept_tree.py`(지도 프롬프트와 예시의 일치), `tests/contracts/test_map_tree.py`, `tests/runner/test_root_front.py`.
- 실제 출제로 확인하는 것은 다음 강의 출제 때다. 이 변경에서는 실행하지 않았다.
