# Main-Quiz 약리 블럭 UI 복원 — 구현 계획

## 변경 범위·대상 파일·순서
1. web/src/bank/RootLearning.tsx·RootSolve.tsx·RootToday.tsx·main-quiz.css에서 기존 BankSolve의 카드/하단바 구성을 재사용하고 답 입력을 없앤다. 관리·부가 기능은 접고 저장 오류와 재시도는 보존한다.
2. RootSolve와 web/src/types/rootLearning.ts에 4단계 평가·1~4/Space/Enter/Z 입력을 연결한다. server/app/routes/root_learning.py 및 필요한 app/root_learning/{policy,state}.py에서 네 평가를 별도 저장하며 도움 여부와 과거 사건 호환을 유지한다. 과거 사건에는 새 평가를 소급하지 않는다.
3. server/app/root_learning의 표시 전용 모듈에서 원본 보존본과 문항별 페이지 근거를 대조하고 revealed_answer에 연결한다. web의 표시 전용 컴포넌트에서 해당 쪽을 렌더링한다. 새 PDF 표시 의존성이 필요하면 웹 패키지/잠금 파일을 함께 고정한다. 서버에서 이미지/원본을 새로 게시하거나 운영 저장소에 쓰지 않는다.
4. RootMap.tsx에 실제 concepts/relations 기반 개념 그래프를 표시한다. 관련 목표·상태를 연결하고 세부 검수/출제포인트 표는 접는다. 기존 ConceptMap은 변경 없이 참고/재사용한다.
5. GuidePage의 새 Main Quiz 안내와 관련 웹/서버/브라우저 검사를 갱신한다. 수정 파일이 범위를 넓히면 먼저 dashboard 중복 확인·갱신을 다시 한다.

## 검사 명령과 성공 조건
web: npm run typecheck, npm run build, node --test tests/main-quiz-render.test.cjs 및 새 표시/입력 회귀 검사.
server-regression: 프로젝트 server 가상환경에서 -m tests를 사용하여 root_api, root_exposure, root_adaptive, main_quiz_choices, root_preservation, route_contract 및 새 평가/슬라이드 검사를 파일별 격리 실행한다. 임시 SQLite/로컬 저장소를 쓰고 운영 .env로 연결하지 않는다.
browser: 합성 자료와 격리 API에서 직접 답 입력 없음, Space→4개 버튼→3/4 평가→다음 문제, 지도 열기 후 평가 가능, Z 취소, 새로고침/재시도/두 탭 충돌, 실제 PDF 해당 쪽 렌더링, 실패 표시, 개념 노드/선과 모바일 화면을 확인한다. 사람의 운영 학습기록을 테스트로 만들지 않는다.
위 실제 명령은 scripts/development.py verify의 web/server-regression/browser 근거로 저장한다. 구현이 없으므로 현재 어떤 검사도 통과로 기록하지 않는다.

## 위험·복원·승인할 범위
2026-11-07 사용자 “응, 그 계획대로 진행해줘”로 이 계획을 승인했다. 후속 지시 “언제나 1,2,3,4 다 선택 가능”을 적용하여 답 공개 후 네 평가를 모두 허용한다. 도움 열람은 보조 기록으로 보존한다.
복습 일정/독립 회상은 표시와 연결되므로 새 네 단계의 사건을 별도로 보존하고 과거 해석을 유지하는 것이 핵심 위험 관리다. 문항/운영 DB/공개 범위를 바꾸지 않는다. UI 복원과 관련 읽기/평가 호환 수정만 포함한다.
구현·검사·리뷰 후 PR로 제시한다. 병합 시 일반 코드 자동 배포가 실행된다는 점을 명시하며, 현재 계획 준비를 운영 배포 완료로 표현하지 않는다. 문제 발생 시 이 변경의 코드만 되돌리고 원본과 학습 사건은 보존한다.
