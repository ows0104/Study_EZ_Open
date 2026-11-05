# 연결 중심 학습 로컬 시범

`web`에서 `npm run pilot` 실행 후 http://127.0.0.1:5186/connection-pilot.html 을 연다.
빌드: `npm run pilot:build` → `web/pilot-dist` (운영 dist와 별도).
검사: `npm run typecheck`, `npm run pilot:test`.

첫 10묶음은 2026-11-03 대화의 질문·답·설명 초안을 옮겼다. 원래 초안은
`docs/changes/2026-11-02-cholinergic-rebuild/content-review.md`이고 문항 참조는 data.ts에 있다.
PILOT ID는 운영 Q/LNK/D ID가 아니다. 의학 검수·독립 포인트 대조 완료를 주장하지 않는다.

첫 답 공개 전 후속 질문·정답·지도는 학습 화면에 렌더링하지 않는다.
지도 탭은 답 포함을 명시하고 노출 여부를 저장한다. self-report는 숙련 인증이 아니다.
원래 답 입력은 공개 후 고정하며 목록은 항목별로 확인한다. 열람 수와 회상 표시는 분리한다.

서버·AI·운영 학습 API를 호출하지 않는다. 전용 revision 키로 localStorage에 저장하며
파손된 저장값은 덮어쓰지 않고 임시 모드 경고를 표시한다. 새 판은 이전 판을 승계하지 않는다.
결과 JSON은 명시적 내려받기만 제공한다. 운영 이용현황은 아직 연결하지 않는다.

UI 시범 완료 범위는 10묶음이다. 49문항 전체 적용, 정식 연결 계약과 생산 파이프라인 결합,
중요도 기반 반복·복습, 운영 화면·개인 학습기록 연동은 후속 범위다.
