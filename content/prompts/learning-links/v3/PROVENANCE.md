# v3 prompts — provenance

각 파일은 단계 틀(새로 쓴 첫 부분) 뒤에 /2 프롬프트 문단을 그대로 옮긴 것이다. 판정 원칙을 새로 짓지 않는다.
원본이 바뀌면 같은 문단을 다시 옮긴다. tests/quizbank/test_root_generation_v3.py가 옮긴 문단이 원본과 같은지 확인한다.

| 파일 | 옮긴 문단(빈 줄로 나눈 문단 번호, 0부터) |
|---|---|
| coverage.md | source-v2.md [1, 2, 4] |
| map-check.md | source-v2.md [3, 6, 10] |
| item-review.md | source-v2.md [5] |
| add.md | author-v2.md [4, 5, 6, 7, 8, 9, 12] |
| fix.md | author-v2.md [4, 5, 6, 7, 8, 9] |
| point-supplement.md | point-extract-v3.md 첫 목록, 「중요도 근거」 절(notebook_profile 앞까지), 범례 문단 |
| supplement-normalize.md | extract-v2.md [1, 2, 3, 4, 마지막] |
| brief-fix.md | author-v2.md [1], extract-v2.md [끝에서 둘째] |
| context.md | 옮긴 문단 없음. automation/context-v2.md의 세 확인 항목과 contamination·incomplete 구분을 충돌 기록마다 판정하도록 새로 썼다(docs/changes/2026-11-10-gen3-item-scope) |

author-v2.md [10](clinical_conflicts는 「모든 conflict_id마다」 facts)은 은행 전체를 한 번에 쓰는 단계의 규칙이라 옮기지 않는다.
add.md·fix.md는 그 문단을 「## 충돌 (이 단계 범위)」로 바꿔 썼다: 새 충돌만 쓰고 기존 충돌은 다시 쓰지 않는다. 뒤 절반(facts에 넣을 것·뺄 것)은 원문과 같다.
그대로 옮겼을 때 261102_02(2026-11-10)의 추가 출제가 CF01–CF03 facts를, 고치기가 CF03을 다시 써 두 번 멈췄다. 코드는 그런 재기록을 받지 않고 기록만 한다.

context.md가 context-v2.md와 다른 점은 둘이다.
- 판정이 기록 하나·문항 하나에만 미친다. context-v2.md는 강의 전체에 값 하나를 냈고, 261102_02(2026-11-10)에서 세 기록의 글로 134문항이 멈췄다.
- 경계를 적었다: 「현재 정답은 A다」처럼 지금 문항이 쓰는 답은 facts에 있어야 하는 내용이고 검수 이력이 아니다. add.md·fix.md는 facts에 「현재 답의 관계」를 쓰라고 하는데 context-v2.md는 「저작 이력」을 오염으로 봐서, 같은 세 기록이 한 번은 확인, 한 번은 오염으로 판정됐다.
