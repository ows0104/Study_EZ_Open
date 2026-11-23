# 관리 페이지 로딩 속도 — 배포 준비

## 코드 리뷰·검증 결과

검토한 경계:

- 숫자 전용 경로와 목록의 수가 갈리지 않는가 — 신고는 같은 함수(`_tally`), 카드는 같은 줄(`_flagged_runs`)에서
  세고, 검사가 세 시점(아무도 안 봄 · 전부 판정 · 뺀 카드와 새 카드가 섞임)에서 둘을 맞대 본다.
- 신고함이 그림을 쓰는가 — `BankReportTab`은 문면·선지·답만 그린다. 사본에서 빠지는 것은 `png_base64`뿐이다.
- 사본 캐시를 밀어내지 않는가 — 캐시는 지금 공개 판에만 쓰고(학습률 계산과 같은 키), 옛 판은 칸에서 읽고 버린다.
- 학생이 새 경로를 읽을 수 있는가 — 둘 다 `require_admin`, 검사가 403을 확인한다.

검사:

- 재현: `test_root_personal`의 「신고함은 원본을 읽지 않는다」 단언은 고치기 전 `feedback.py`에서 실패한다
  (`SELECT root_content.document …` 한 건이 잡힌다). 고친 뒤 통과.
- 서버 `-m tests` 전부: 결과는 아래 「실행 기록」.
- 웹 `tsc -b --noEmit` 통과, `npm run build` 통과.
- 로컬 미리보기(격리 SQLite, 가상 데이터): `/admin`이 뜰 때 나간 요청은 `overview`·`prequiz-jobs`·`users`·
  `card-review/count`·`bank-feedback/count`. 목록 두 요청은 각 탭을 처음 열 때 나가고, 다른 탭에 다녀와도
  다시 나가지 않는다. 신고를 「반영했다」로 닫으면 목록을 다시 읽고 탭 옆 숫자가 사라진다.
  (개발 모드는 StrictMode라 요청이 두 번씩 보인다. 배포 빌드는 한 번이다.)

남은 위험:

- 운영에서의 실제 시간은 배포 뒤에 잰다. 로컬은 요청 구성만 확인했다.
- `card-review` 목록은 걸린 편마다 질의하는 구조 그대로다. 이제 탭을 열 때만 돈다.

### 실행 기록

- 서버 `-m tests` 전부(2026-11-23, 메인 체크아웃 `server/.venv`, `PYTHONPATH=..`): 166개 중 164개 통과.
  실패 2개 `test_root_map_tree`·`test_root_map_tree_v3`는 이 venv에 `pymupdf`(`fitz`)가 없어 검사 파일 import에서
  멈춘 것이다(`ModuleNotFoundError`). 이번 변경이 건드리지 않은 경로이고, 판정은 CI(`Tests and build`)에 맡긴다.
- 바뀐 범위만 따로 기록: `card_edits`·`root_personal`·`route_contract`·`test_bank` 모두 종료 0
  (`runs/_development/2026-11-23-admin-page-load/`). 새 단언(숫자 = 목록, 학생 403, 원본 안 읽기)이 로그에 PASS로 찍힌 것을 확인했다.

## 배포 대상 버전·순서·데이터 변경

- 대상: 이 브랜치(`claude/admin-page-load`)의 PR을 master에 병합한 커밋.
- 순서: master 병합 → 검사 → Cloud Run(API) → Pages(웹). 새 화면이 부르는 새 경로 둘은 API가 먼저 나가야 선다.
  옛 화면은 기존 경로만 부르므로 어느 순서에서도 깨지지 않는다.
- DB·스키마·저장 데이터 변경 없음.

## 배포 후 확인·롤백·필요한 사람 승인

- 확인: 운영 `/admin`을 열어 Resource Timing으로 `overview` 시간과, 화면이 뜰 때 `bank-feedback`·`card-review`
  목록 요청이 없는 것을 본다. 「Quiz Bank 신고」 탭을 열어 Main-Quiz 신고의 문면이 그대로 보이는지 본다.
  라이브 openapi에 `…/count` 경로 둘이 있는지 본다.
- 롤백: PR revert, 또는 이전 Cloud Run revision·Pages 배포.
- 사람 승인: 필요 없음(「사람에게 묻는 것」에 닿지 않는다). Ready·병합은 사용자가 정한다.
