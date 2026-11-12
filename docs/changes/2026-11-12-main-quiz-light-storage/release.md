# Main-Quiz 저장 방식: 그림 뺀 사본 칸·그림 표 — 배포

## 운영 DB 채우기 (2026-11-12, 사용자 「Run it now」)
이 브랜치 코드로 `server/.env`(운영)에 대해 실행했다.

1. `main-quiz-light`(보기만): 표·칸 없음, 채울 판 34개.
2. `main-quiz-light --apply`: `root_image` 표 생성, `root_content.light` 칸 추가, 18판 채움(그림 172개).
   19번째 판(감염과 면역/261105_02)에서 그림 12개를 한 번에 보내다 pooler 연결이 끊겼다(`SSL error: bad length`).
   그 판의 트랜잭션은 되돌려졌다. → 그림을 한 줄씩 넣게 고침(b3aeb7e9) 뒤 다시 `--apply`: 남은 16판 채움(그림 147개).
3. 다시 보기만: 채울 판 0개. 읽기 전용 확인: 34판 전부 `light == stored(document)`, 그림 319개 전부 원본과 같음, 불일치 0.
   DB 620.5 MB → 746.9 MB. 원본 `document`·학습 기록은 읽기만 했다.

## 배포 순서·관측·롤백
- 이제 코드 병합 가능: #131(웹) → #134 → #135(base를 master로 바꾼 뒤). master 병합이 API·웹을 자동 배포한다.
- 병합 전까지 운영(옛 코드)이 새로 공개하는 판은 `light`가 비어 있다 — 새 코드는 원본으로 동작하고, `main-quiz-light --apply`를 다시 돌리면 채운다.
- 배포 뒤 볼 것: 시작 로그 「가벼운 사본 N편 … (x s)」, `GET /api/root-learning`·`POST …/events` 지연, 「Memory limit」 재발 여부.
- 롤백: 코드 revert 또는 이전 Cloud Run revision. 칸·표는 옛 코드에 무해하므로 남겨 둔다.
