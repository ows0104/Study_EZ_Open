# Main-Quiz 보충 포인트 ID 충돌 수정

## 문제와 사용자 효과
2026-11-13 261113_02 소아감염(윤기욱) 연결 자동출제가 `v4-supplement-normalize` 뒤에서
「연결 자동출제 보류: v3 extend: exactly the supplement points」로 멈춰 Quiz Bank(Main-Quiz)를 만들지 못했다
(로그 `runs/agent.261113_02.log`, 산출물 `runs/_root-generation/fea11389e81c43ddacc2b841a78a6440/generation/`).

원인:
- 출제 포인트 문서는 P001–P087(87개).
- `v4-brief-fix`가 포인트가 없는 목표 T088–T093을 고치며 brief에만 P088–P093을 만들었다. 포인트 문서에는 없다.
- 목표 밖 문항 Q092가 보충 포인트로 판정되자 `attach_points`가 **포인트 문서의** 최댓값+1로 P088을 매겼다.
- `extend_brief`가 brief에 이미 P088이 있으므로 거부했다. 모델 출력(supplement, supplement-normalize)은 정상이었다.

brief-fix가 포인트를 만들고 보충 포인트도 생기는 강의라면 어디서든 같은 이유로 멈춘다.

## 범위와 성공 기준
- 보충 포인트의 새 ID는 포인트 문서와 brief 어느 쪽에도 없는 번호(둘의 최댓값 다음)다.
- 기존 포인트·tier·brief 내용은 바뀌지 않는다. 충돌이 없는 경우의 번호는 지금과 같다.
- 261113_02를 다시 돌리면 완료된 단계는 재사용되고 supplement-normalize만 새 ID로 다시 호출된다.

## 근거·미정 사항
- 사용자 요청(2026-11-14 채팅): 「여기서 고쳐줘」 — 원인 보고(ID 충돌, 양쪽 최댓값 다음 번호로 고치는 방향) 직후.
- brief-fix가 출제 포인트 추출에 없는 포인트를 만드는 것 자체를 허용할지는 이번 범위 밖이다(보고만 함).
