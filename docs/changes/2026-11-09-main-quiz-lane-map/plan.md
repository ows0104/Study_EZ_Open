# Main-Quiz 개념 지도 가지 보기 — 구현 계획

## 변경 범위·대상 파일·순서
1. `web/src/bank/rootMapTree.ts`
   - `buildTree`, `ancestors`, `targetStatus`는 그대로 둔다.
   - 왼→오 `layout`·`SIZE`는 열 배치에 쓰는 순수 함수로 바꾼다. 하는 일은 셋이다.
     - 최상위 노드를 열로 나눈다(9개 이상이면 줄을 감싼다).
     - 각 열의 개념 목록을 깊이 순서로 낸다.
     - 개념별 문항 id를 낸다.
2. `web/src/bank/RootMap.tsx`
   - 그리는 부분을 바꾼다.
     - 제목 카드, 열 머리, 들여쓴 개념 줄과 상태 점, 펼친 문항 줄을 그린다.
     - 가지·연결선은 SVG 겹침층에 그린다.
     - 데스크톱은 확대 캔버스, 모바일은 세로 목록이다.
   - 유지하는 것은 다음과 같다.
     - 확대·이동·키보드 처리
     - 찾기
     - 패널
     - 「목록으로 보기」와 「자료 범위」
   - 버튼은 ＋ − 전체 현재 문제 문항 펼치기 접기 연결선 전체 크게 보기다.
3. `web/src/bank/main-quiz.css`(Main-Quiz 지도 스타일이 있는 곳): 열·줄·상태 점·선택/흐림·연결선·전체 화면·모바일 스타일. 옛 `main-quiz-tree-*` 중 쓰지 않게 되는 규칙은 지운다.
4. `web/tests/root-learning.test.cjs`, `web/tests/main-quiz-map-tree.test.cjs`(layout 단위 검사 → lanes)
   - 옛 SVG 노드 수 단언(`g[role=button]` 7, `path.main-quiz-tree-edge` 6)을 새 구조에 맞게 바꾼다.
   - 수용 기준 1–3을 단언으로 더한다.
5. `docs/changes/2026-11-09-main-quiz-lane-map/release.md`에 검사·스크린샷·배포 결과를 적는다.

건드리지 않는 것:
- `RootLearning.tsx`(Main-Quiz 지연 작업 행의 파일)
- `GuidePage.tsx`(UI 개편 작업 행의 파일)
- 서버·계약·DB
- Quiz Bank `ConceptMap.tsx`

## 검사 명령과 성공 조건
- `npm --prefix web run typecheck`: 0 오류
- `npm --prefix web run build`: 성공
- root-ui 브라우저 검사: 로컬 격리 서버와 fixture로 `node --test web/tests/root-learning.test.cjs`를 돌린다. `scripts/check_connection_generation.py`와 같은 방식이고, 운영 DB는 쓰지 않는다.
  - 전부 통과해야 한다.
  - 데스크톱·모바일 지도 스크린샷을 남긴다.
- 수동 확인: 로컬 웹에서 감염병리1형 fixture와 기존 fixture를 1600×900과 390×844로 열어 수용 기준 1–3을 눈으로 확인한다.
- 각 검사는 `scripts/development.py verify`로 기록한다.

## 위험·복원·승인할 범위
- 위험 1: 최상위가 아주 많은 평평한 판에서는 열 감싸기 뒤에도 첫 화면 배율이 낮을 수 있다.
  - 이때는 배율 하한을 두고 위쪽부터 보여 준다.
  - 기존 「목록으로 보기」는 남긴다.
- 위험 2: 기존 흐름 검사(지도 왕복·새로고침 재개)의 선택자가 바뀐다. 접근성 이름(`개념 트리` group, 버튼 이름)은 유지해서 영향을 줄인다.
- 복원: 웹 커밋 revert. 서버·DB 변경이 없다.
- 승인 범위: 사용자의 작업 요청(2026-11-09 「가지 보기로」)이 구현 승인이다(개발 루프 2026-11-08 기준).
  - 범위는 위 파일들의 구현·검사, 커밋·push·PR, master 병합(자동 API·Pages 배포)이다.
  - 서버·DB·학습 기록·공개 범위 변경이 없어 「사람에게 묻는 것」에 닿지 않는다.
  - 되돌리기는 git revert와 이전 Pages 배포다.
