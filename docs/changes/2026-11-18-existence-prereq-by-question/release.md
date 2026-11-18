# Main-Quiz 존재 선행: 목표 단위 대신 문항 단위로 끌어오기 — 배포 준비

## 코드 리뷰·검증 결과
- 새 검사 `server/tests/test_root_existence_links.py` 통과(문항 단위 끌어오기·풀어 주기·오늘 목록 밖 전제·지도 선행·links 없음·
  `existence_links` 포인트/놓이지 않은 문항/판에 없는 간선·서버의 생성 기록 읽기). 기존 `test_root_prereq_release`(links 없음) 그대로 통과.
- 서버 검사(`-m tests` prereq·root·main_quiz·route_contract, development.py verify 기록): prereq 2/2·main_quiz 9/9·route_contract 1/1 통과,
  root 53/55 — 실패 2개(`test_root_map_tree`·`test_root_map_tree_v3`)는 서버 venv에 `pymupdf`/`fitz`가 없어 import에서 멈춘 환경 문제로 이 변경과 무관.
- 검토: links가 None이면 이전 코드와 같은 경로(목표 선행 한 번 돌고 끝). links가 있으면 존재 간선은 목표 단위로 건너뛰고,
  문항 단위 끌어오기와 지도 선행을 늘지 않을 때까지 번갈아 돈다(`expanded`·`selected`가 단조라 끝난다). 순서(`emit`)·
  문항 사이 선행(`order_plan`)은 그대로. 생성 기록 읽기 실패·없음은 None → 이전 규칙.
- 운영 사본 재현(읽기 전용 트랜잭션 → 로컬 계산, 2026-11-18 12:00 KST, 261110_02 판 `auto-e45e0758…`, 오늘 학습자 1명,
  칩 Essential·Core·Important, 아침 기록). 학습자가 오늘 Q102·Q107을 「개인 제외」해서, 재현에서는 둘을 준비된 것으로 두었다.
  - 이전 규칙: 137과제, 선행으로 끌려온 Optional 28개(Q107·Q100·Q117·Q111·Q162·Q048 등 포함).
  - 새 규칙: 120과제, 선행으로 끌려온 Optional 11개. **Q107 없음.** 남은 11개는 모두 오늘 목록 문항의 전제를 답한다:
    Q102←Q012, Q106←Q114, Q160←Q014, Q161←Q017, Q165←Q042·Q043, Q116←Q034 등, Q028←Q119, Q112←Q034·Q119,
    Q131←Q056, Q176←Q131(연쇄), Q167←Q054, Q168←Q057·Q059.
  - Q102가 남는 것은 전제 판정이 Q102를 E1A·E1B 존재 문항으로 기록했기 때문이다(intent 범위 밖, 출제 쪽).

## 배포 대상 버전·순서·데이터 변경
- 서버 코드만(planning·content·routes). 웹·DB 스키마·운영 데이터·판·학습 기록·프롬프트·생성기 변경 없음.
- master 병합 → 자동 배포(검사 → Cloud Run → Pages).

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 운영 `/health` SHA. 이미 시작한 오늘 흐름은 고정이라, 다음 학습일(또는 칩을 바꿀 때 뒷부분)부터 반영된다.
- 롤백: `git revert` 뒤 재배포.
- 승인: 사용자 「응, 고쳐줘」(2026-11-18). 되돌릴 수 있는 코드 배포라 따로 묻지 않는다.
