# 모아풀기 시작 화면 선택지 — 배포 준비

## #219 병합 후 rebase(2026-11-18)
- master의 #219에 e198b5c8(남은 수 비례 무작위 강의 고르기, 새로고침 전에 끝낸 강의를 마침 화면에 남기기)이 더해져 병합됐다.
  RootBatch.tsx·root-batch.test.cjs가 충돌했고 이 작업 쪽으로 풀었다. 강의 고르기는 이 작업의 순서대로/섞어서(섞어서 = 같은 남은 수 비례, 결정적)가 대신한다.
- 마침 화면 고침은 옮겼다: `GET …/mix`가 오늘 다 푼 모아풀기 회차를 `closed`로 함께 주고(spec의 응답에 칸 하나 추가, 같은 파일·같은 범위),
  같은 조건으로 이미 끝낸 강의는 마침 화면 결과에 남는다. `root_mix`·브라우저 검사에 그 경우를 넣었다.

## 코드 리뷰·검증 결과
- 서버(격리 sqlite, `server/`에서 `.venv/Scripts/python.exe -m tests <이름>`): `root_mix`(새, 옛 판 API 흐름)·`root_mix_v4`(새, /4 판 과제별 분류)·
  `route_contract`(새 경로 2개 등록)·`root_api`·`root_focus`·`root_photo_order`·`root_learning_v4`·`root_mine` 통과.
- 웹: typecheck·build 통과.
- 브라우저(`python scripts/check_root_learning.py --check root-batch`, 격리 fixture 두 강의) 2개 통과:
  기본값 0문항 → 미열람 문항 보기 6, 강의별 칩으로 한 강의 Core 끄기 → 0·전체 칩 「일부」 → 전체 칩으로 되돌림, 마지막 전체 칩 잠김,
  순서대로(A1→A3→B1…), 강의를 건넌 Z, 새로고침 뒤 같은 조건이면 재개(다른 조건이면 새 회차 자리), 마침, 기존 학습률 무시로 오늘 푼 6문항이 다시 셈,
  섞어서(모든 문항 한 번씩, 강의 사이·안 모두 섞임), 390px 가로 넘침 없음, 콘솔 오류 0.
- `--check root-ui` 9개 통과(강의 하나 Main-Quiz 회귀 없음).
- 브라우저 창에서 시작 화면 확인: 꺼진 칩·「일부」 칩·강의별 펼침 화살표.
- 리뷰에서 고친 것: 섞어서의 강의 사이 순서가 FNV 해시 상관으로 한 강의를 몰아 냈다 → 남은 수 비례 추첨(모든 번갈아 놓기 같은 확률, 2만 회 모의 20가지 각 ≈1000).
  오늘 답만 보고 평가하지 않은 문항이 「복습 대상」으로 다시 잡혔다 → 오늘 건드린 과제는 「나중」.
- 미실행: #219의 `study-mix-pick.test.cjs`·`study-management`(이번에 StudyOverview를 고치지 않음).

## 배포 대상 버전·순서·데이터 변경
- 대상: `claude/multi-lecture-review`(#219 `feat/main-quiz-batch` 위). #219가 먼저 병합돼야 한다.
- DB 스키마·migration 없음. 새 행은 기존 `root_session`(state.mix)·`root_event`(kind='start') 형식.
- 서버(새 경로)와 웹이 같이 바뀐다. 자동 배포 순서(API 먼저 → 같은 SHA 웹)를 따른다. 웹이 먼저 나가면 `/mix`가 404라 강의 줄이 「열 수 없음」.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 강의 목록에서 Main-Quiz 강의 둘 체크 → 모아풀기 → 수·칩·체크 반영, 시작 후 강의 화면 「오늘 학습」이 모아풀기 회차로 바뀌지 않는지.
- 롤백: git revert PR. 남은 `state.mix` 회차는 옛 서버에서 그 강의의 오늘 흐름으로 이어 풀 수 있을 뿐 기록은 그대로.
- 필요한 승인: master 병합(=운영 자동 배포)은 사용자 승인 후.
