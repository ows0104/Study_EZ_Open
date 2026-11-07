# Main-Quiz 참고슬라이드 복구·트리형 개념지도 — 구현 계획

## 변경 범위·대상 파일·순서
1. server/app/storage.py: `open_stream`에 선택적 바이트 범위(R2 get_object Range / 로컬 seek).
2. server/app/routes/root_learning.py: 읽기 전용 출처 경유 경로. server/app/root_learning/evidence.py: pdfSlides url을 경유 주소로. server/tests에 권한·SHA 불일치·Range·416 검사, test_route_contract 갱신.
3. web/src/bank/RootPdfSlides.tsx: getDocument에 인증 헤더, 경유 주소 사용, 실패 시 원본 열기 안내 유지.
4. web/src/bank/RootMap.tsx(+ 필요 시 RootMapTree 분리)·main-quiz.css: 트리 배치·확대/이동·단계별 펼침·옆 패널·검색·현재 문제 강조. 기존 상세 접기(자료 범위·출제포인트)는 유지.
5. 문서: 이 폴더 implementation/release, server storage 주석에 CORS 사정 추가.

## 검사 명령과 성공 조건
- web: npm run typecheck, npm run build, 기존 node --test tests/main-quiz-render.test.cjs.
- server-regression: server .venv `-m tests root`, `-m tests route_contract`, 새 출처 경유 검사(임시 SQLite·로컬 저장소, 운영 .env 미사용).
- browser: 격리 로컬 API·웹에서 261104_02 공개 판과 같은 형태의 자료(로컬 보존본 curated-result + S1.pdf)를 등록해 답 공개 → 실제 PDF 쪽 렌더링, 지도 트리 확대/주제 펼침/패널/검색/현재 문제 강조, 모바일 폭을 확인하고 스크린샷을 남긴다. 운영 학습 기록에 쓰지 않는다.

## 위험·복원·승인할 범위
- 위험: 22.7MB PDF가 API를 지나간다 → Range로 필요한 부분만, 브라우저 캐시. Cloud Run 시한은 이미 600초.
- 복원: 코드 PR revert만으로 되돌린다. 데이터 변경 없음.
- 승인 요청 범위: 위 파일의 로컬 구현·검사·리뷰·PR 생성까지. master 병합(=운영 자동 배포)과 감염병리1 학생 공개(공개 설정 변경)는 각각 별도 승인.
