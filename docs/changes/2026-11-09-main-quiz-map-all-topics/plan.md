# Main-Quiz 개념 지도 빠진 주제 복원 — 구현 계획

## 변경 범위·대상 파일·순서
1. `web/src/bank/rootMapTree.ts`: `buildTree`에 답 노드 판정, 문항 주제 선택, 남은 주제 배치를 넣는다. 머리 주석도 고친다.
2. `web/tests/main-quiz-map-tree.test.cjs`에 단언을 더한다.
   - Map 판 모양: C 계층과 F 답 노드, 보조 개념, 문항 없는 개념, 고립 개념
   - 답 노드 판정, 문항 주제, 숨던 주제 노출, 고립 개념 제외
3. `web/tests/root-learning.test.cjs`: fixture에서 바뀌는 수가 있으면 맞춘다(B가 주제로 보이는지 등).
4. 이 폴더의 `release.md`에 결과를 적는다.

## 검사 명령과 성공 조건
- `npm --prefix web run typecheck`: 0
- `npm --prefix web run build`: 0
- `node --test web/tests/main-quiz-map-tree.test.cjs`: 모두 통과
- root-ui 브라우저 검사: 격리 fixture(SQLite·로컬 저장소)로 `root-learning.test.cjs`가 모두 통과해야 한다.
- 실제 데이터: 감염병리1 map-tree-26110803 지도 응답을 fixture 지도 경로에 넣는다.
  - 주제 75개와 결핵↔AFB 연결선을 스크린샷으로 확인한다.

## 위험·복원·승인할 범위
- 위험: 다른 판에서 답 노드 판정이 진짜 개념을 답으로 오인할 수 있다.
  - 그 경우 그 개념이 숨는 것은 지금과 같은 결과라 더 나빠지지 않는다.
  - 반대로 답 노드가 주제로 보이면 긴 문장 노드가 생긴다. 운영 Main-Quiz 판은 감염병리1 하나뿐이고, 실측 오분류는 0이다.
- 복원: 병합 커밋 revert.
- 승인: 사용자 「고쳐줘」(2026-11-09)가 구현 승인이다.
  - 범위는 위 파일의 구현·검사, 커밋·PR, master 병합(자동 배포)이다.
  - 서버·DB 변경이 없어 「사람에게 묻는 것」에 닿지 않는다.
