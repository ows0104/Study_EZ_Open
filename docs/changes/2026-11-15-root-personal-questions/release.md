# Main-Quiz 내 문제(추가·복사 후 수정)와 뒷면 메모 — 배포 준비

## 코드 리뷰·검증 결과
- 서버 `-m tests root_mine`: 통과. 만들기·복사(그림 sha 유지)·고치기·지우기, 같은 requestId 멱등·다른 내용 409,
  빈 글 422·없는 기준 404·상한 409, 계획·오늘 흐름에 들어감(refocus), 학습률·카드 수·요약·칩 개수 불변,
  다른 사용자에게 안 보임·못 고침, 메모 저장·답면(회차·미리 읽기)에만·멱등, 내 문제에 대한 내 중요도·개인 수정 API 404,
  캐시된 판 사본 불변, 이전 정책 판은 409·메모는 가능·새 판으로 안 옮김.
- 서버 `-m tests root`: 46개 중 44개 통과. 실패 2개(`test_root_map_tree`, `test_root_map_tree_v3`)는
  이 로컬 서버 venv에 `pymupdf`(fitz)가 없어 `quizbank/connection_generate.py`를 import하지 못한 것 — 이번 변경이
  건드리지 않은 파일·import다. CI(PR 검사)에서 다시 본다.
- 서버 전체·Main-Quiz 브라우저 회귀(`scripts/check_root_learning.py --check root-ui`): 아래 결과 칸.
- 웹 `npm run typecheck`·`npm run build` 통과. `python scripts/map_numbers.py --check` 통과.
- 브라우저(로컬 합성 v4 판, 격리 DB): 복사해서 고치기(원문 채움) → 오늘 목록 4→5, 「내 문제」 표시·내 중요도 숨김·
  해설 표시, 새 문제(빈 칸), 뒷면 메모 쓰기·Ctrl+Enter 저장(입력 중 숫자키가 평가로 가지 않음), 내 문제 지우기 →
  계획에서 빠지고 카드 총수 4 그대로.

## 배포 대상 버전·순서·데이터 변경
- 코드만(API·웹). DB 스키마·migration·운영 데이터 수정 없음. 새 기록은 사용자 화면에서 쌓이는
  `root_event`(kind `mine`·`memo`)뿐이다.
- master 병합 → 자동 검사 → Cloud Run(API) → Pages(웹). 옛 웹+새 API, 새 웹+옛 API 모두 동작한다
  (새 칸이 없으면 메뉴·메모를 그리지 않는다).

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 라이브 openapi에 `/mine`·`/memo` 경로, 내 계정에서 root-generation/4 판 하나로 복사→풀이→메모→지우기.
- 롤백: git revert + 이전 Cloud Run revision·Pages 배포. 쌓인 `mine`·`memo` 이벤트는 옛 코드가 무시한다.
- 승인: 사람에게 묻는 항목(스키마·운영 데이터·공개 범위)에 닿지 않는다. 사용자 요청이 구현 승인.
