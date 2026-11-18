# Main-Quiz 순서 맞추기 화면 — 배포 준비

## 코드 리뷰·검증 결과
- 계약 `tests/contracts/test_root_order_contract.py` 12개, 생성기 `tests/quizbank/test_root_order.py` 5개,
  러너 `tests/runner/test_root_order_publish.py` 4개와 게시 뒤 호출 순서를 본 기존 러너 검사(선지 다음에 판정) 통과.
  루트 `tests/contracts`·`tests/quizbank` 전부 통과, `tests/runner` 871 통과(`test_desktop_control`의 바로가기 설치 검사 하나는
  checkout 루트의 `.venv`를 찾아서 새 worktree에서는 돌지 않아 뺐다 — 이 변경과 무관). 게시 직후 하위 프로세스 목록을 보는
  기존 검사(`test_root_front*.py`)에는 선지처럼 판정 단계도 가짜로 막았다.
- 서버 `server/tests/test_main_quiz_order.py` 통과: 판·지문·순열이 어긋나면 지금처럼 선지, 맞으면 order_items만, 앞면에 정답 순서 없음, 답면에 orderCorrectIds.
  `-m tests main_quiz` 10/10, `route_contract` 1/1, `root` 52/54(남은 둘 `test_root_map_tree`·`_v3`는 빌린 venv에 pymupdf가 없어 import에서 멈춤 — 이 변경과 무관, CI에서 확인).
- 웹: typecheck 통과, `tests/root-order.test.cjs` 4/4, 브라우저 고정물 `tests/root-order.html` 22/22
  (객관식 모드 처음부터·숫자 키 놓기/빼기·Backspace·Space 응답·답면 자리 비교·주관식 V 펴기/접기·도움받은 풀이 기록).
  데스크톱·휴대폰 폭(375px) 화면 확인, 가로 넘침 없음.
- 실데이터: 261110_02(아데노·폭스바이러스) 판에 판정을 `--no-upload`로 한 번 돌림. 대상 나열 33문항 중 순서형 1(Q174 복제주기, 저장 순서 그대로), 나머지 32는 「독립된 특성·목록」으로 아님. Codex 호출 1회 42초.

## 배포 대상 버전·순서·데이터 변경
1. master 병합 → API·웹 자동 배포. asset 종류 `root_order`가 생기고, 판정이 없는 판은 지금과 같다.
2. 러너 PC 재설치(.runtime) → 새로 게시되는 판은 선지 다음에 판정이 붙는다.
3. 이미 게시된 판: `python -m runner.root_order --all-published --subject 감염과 면역 --missing` (강의당 Codex 1회). 사람 승인 뒤.
DB 스키마·문항·판·학습 기록·선지 asset 변경 없음.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 261110_02 Q174가 객관식 모드에서 순서 맞추기로 나오는지, 다른 나열 문항은 선지 그대로인지.
- 롤백: 문제 줄만 빼고 asset을 다시 올리거나, asset 삭제(그 판은 지금 화면으로), 또는 커밋 revert.
- 승인: master 병합(=배포), 공개 판 전체 판정·업로드.
