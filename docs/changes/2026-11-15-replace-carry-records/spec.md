# Main-Quiz 재배치 판에 기존 학습 기록 승계 — 명세

대상: 재배치 경로 unplaced-only/1(`quizbank/connection_replace.py`), 판 문서 계약(`studyez_contracts/roots/validate.py`),
요청 packet(`server/app/routes/root_generation.py`). 학습 집계(`state.replay_tasks`)·등록 검사(`content.carried_questions`)의 승계 규칙은 그대로 쓴다.

### R1. 재배치 판이 equivalences를 적는다
- packet의 `carrySources`(R2)에 든 판마다, 새 문서의 방향 d가 그 판에도 있고 그 판의 d 과제 중 하나 이상과 문항 지문이 같으면
  링크 `{revision, from_direction: d, to_direction: d, reason}` 하나를 적는다. reason은 「못 붙은 문항 재배치: 같은 방향·같은 문항 지문」.
- 지문이 다른 문항(고친 문항)은 승계되지 않는다(기존 규칙). 방향 ID만 같다고 잇지 않는다.
- manifest `unplacedOnly.carry`에 판마다 링크 수·이을 과제 수를 남긴다.

### R2. 서버가 packet에 이전 판 지문을 넣는다
- `unplacedOnly` 요청이면 packet `carrySources` = 그 강의의 검토된(`reviewed`) root-generation/4 판 전부(현재 공개 판 포함),
  판마다 `[{direction_id, fingerprint}]`. 오래된 판이 먼저.
- 그래서 이미 교체한 3편을 한 번 더 재배치하면 새 판이 교체 전 판·교체 뒤 판(·중복 재판정 전 판)을 모두 잇는다.

### R3. 한 방향을 여러 판에서 이을 수 있다
- 계약의 「한 새 방향에는 링크 하나」를 「한 (판, 새 방향)에는 링크 하나·한 (판, 이전 방향)에는 링크 하나」로 바꾼다.
  집계는 이미 이벤트를 시간순으로 재생하므로 여러 판 기록이 한 과제에 이어진다.

### R4. 「내 중요도」·「이 문제 제외」도 잇는다 (사용자 「승인, 선택도 승계」, 2026-11-15)
- 같은 링크·같은 문항 지문일 때 이전 판의 선택을 이어 쓴다(`personal_tiers`, `excluded_ids`, `tiers_for`). 시간순으로 마지막 선택이 이긴다.
- 「내 중요도」 이벤트는 지문을 담지 않으므로 서버가 링크된 이전 판의 사본으로 (이전 판, 문항 ID) → 새 문항 ID 표를 만든다.

## 오류 상태
- 링크가 하나도 안 나오면(지문 일치 0) 링크 없이 게시하지 않고 보류한다 — 재배치는 옛 과제를 모두 유지하므로 0이면 이상이다.
- 등록(`validate_registration`)은 지금처럼 이전 판이 검토된 판인지·잇는 문항이 있는지 다시 확인한다.

## 바꾸지 않는 것
문항·과제·지도·중복 재판정 경로·이벤트 기록. 옛 판과 그 기록은 DB에 그대로 남는다.
