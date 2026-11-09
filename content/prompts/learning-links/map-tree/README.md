# map-tree/1 앞 단계 지시문

Main-Quiz 시범 두 번(감염병리1 26110803, 사슬알균 26110901)의 앞 단계 지시문이다. 시범에서는 스크립트에 직접 짜여 있었다.
`runner/root_front.py`가 관리자 요청(`pipeline: map-tree/1`)마다 쓴다. 근거: `docs/changes/2026-11-09-main-quiz-runner-pipeline/`.

| 파일 | 쓰는 단계 | 붙이는 방식 |
|---|---|---|
| `extract-task.md` | 개념 지도 /3, 포인트 /3 추출 | `map-extract.md` 또는 `point-extract-v3.md` 뒤에 빈 줄 하나를 두고 붙인다 |
| `point-audit.md` | 포인트 대조, 재대조 | 이것만 보낸다. 끝 줄바꿈은 뺀다 |
| `point-repair.md` | 포인트 보완 1회 | `point-extract-v3.md` 뒤에 줄바꿈 하나를 두고 붙인다. 끝 줄바꿈은 뺀다 |
| `point-audit.schema.json` | 대조의 `audit.json` 형식 | — |

- 자리 표시: `$title`(강의 제목), `$first_id`(C001·P001), `$filename`, `$pages`(「S1 1~38쪽과 S2 1~8쪽」). 파이썬 `string.Template` 문법이다.
- **문구는 출제 정책이다.** 구조를 옮기면서 바꾸지 않았다.
  - `tests/runner/test_root_front.py`가 사슬알균 값으로 채운 결과를 확인한다.
  - 비교 대상은 시범이 실제로 보낸 task.md(`tests/fixtures/map_tree_26110901/`)이고, 글자 하나까지 같아야 한다.
- 고칠 때는 승인된 출제 정책 변경으로 한다. 기준 fixture도 그 결정과 함께 바꾼다.
