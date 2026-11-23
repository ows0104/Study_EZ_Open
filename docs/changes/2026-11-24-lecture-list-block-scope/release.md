# 강의 목록 숫자 칸: 고른 블럭의 강의만 계산 — 배포 준비

## 코드 리뷰·검증 결과
- 서버 `catalog`
  - `lecture` 인자가 있으면 열린 강의 중 물은 키만 `allowed`·`overview_data`를 돈다.
  - 모양이 틀린 값만 왔으면 빈 목록이다(전부가 아니다).
  - 인자가 없으면 그대로다.
- 웹
  - `useRootSummaries(keys)`가 키 묶음마다 60초 캐시를 둔다.
  - 키 묶음이 바뀌면 `loaded: false`라, 앞 블럭 값이 새 블럭에 비치지 않는다.
  - 받은 값은 고른 블럭의 행(`inCourse`)에만 쓴다.
- 새 카드: 서버 `question_progress.newToday` = 오늘 계획의 안 본 카드 수다.
  - `reviewDue`와 같은 계획을 쓰므로 중요도 칩을 따른다.
  - `test_root_focus`의 「칩을 바꿔도 단계 수는 그대로」 확인은 단계 수에만 남기고, newToday가 칩을 따르는 것(3→2)을 새로 확인한다.
- 시작 화면: 숫자 칸·막대·오늘 추천은 `questionProgress`(카드)를 쓴다. 접은 자세히 보기만 「학습 목표 기준」임을 밝힌다.

## 검사(2026-11-24 실행)
- 서버(`server/`, 메인 체크아웃 venv, `PYTHONPATH=..`)
  - `-m tests root`: 56/58 통과.
    - 실패 2개는 `test_root_map_tree`·`test_root_map_tree_v3`다. venv에 `pymupdf`가 없는 환경 문제이고 이번 변경과 무관하다.
  - `card`·`mastery`: 모두 통과.
  - 새 `test_root_catalog_scope`는 고치기 전 코드에서 실패하는 것을 확인했다.
  - dev 기록 `verify --check server`(이번 변경이 닿는 6개): exit 0.
- 웹
  - `npm --prefix web run typecheck`: 통과. dev 기록 `verify --check web`: exit 0.
  - 브라우저(vite 5197 + Playwright) `study-loading`·`study-blocks`·`study-management`: 16 통과, 2 실패.
    - 실패 2개는 master(fbd49660)에서도 똑같이 실패한다(11-18 모아풀기 개편 뒤 낡은 기대값).
      - `study-blocks` 「Main-Quiz-only … no batch checkbox」
      - `study-management` 「퀴즈 없음」 대기
    - 같은 이유로 깨져 있던 `study-loading`(행 수 10→11)과 `study-blocks` 가짜 훅 이름은 바로잡아 이번 확인이 실제로 돈다.
      - 블럭 키만 묻기, 다른 블럭은 새 요청과 「…」, 돌아오면 캐시, 새 카드 70장.
  - 새 `tests/root-today-cards.html`: ALL PASSED. `?view`로 그린 화면을 눈으로 확인했다(데스크톱, 목록은 휴대폰 폭 2×2·가로 스크롤 없음).

## 배포 대상 버전·순서·데이터 변경
- master 병합 → 자동 검사 → Cloud Run(API) → Pages(웹).
- DB·스키마·학습 기록 변경은 없다.
- 순서는 상관없다. 옛 웹이 새 API를 만나면 인자가 없어 전부를 받는다. 새 웹이 옛 API를 만나면 옛 API가 인자를 무시하고 전부를 준다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 운영 `/study`에서 `/api/root-learning?lecture=…` 응답 시간을 잰다.
  - 이번 블럭 강의 수 × 약 0.2 s 안팎이어야 한다.
  - 숫자 칸 값이 바뀌기 전과 같아야 한다.
- 롤백: git revert, 이전 Cloud Run revision·Pages 배포.
- 승인: 병합(자동 배포)은 사용자에게 따로 묻는다.
