# Main-Quiz 참고슬라이드 복구·트리형 개념지도 — 구현

## 참고슬라이드
원인: PR16 이후 답 공개 응답의 `pdfSlides[].url`은 R2 서명 URL이고, PDF.js는 이를 `fetch`로 읽는다. R2 버킷 `studyez`에는 CORS 규칙이 없어 운영에서 막힌다(2026-11-07 서명 URL preflight 403 재확인). PR16의 검사는 로컬 저장소(같은 출처)라 드러나지 않았고, 운영 확인은 `<a>` 원본 다운로드(CORS 무관)였다.

- `GET /api/root-learning/lectures/{subject}/{run_id}/sources/{source_id}`: 활성 판을 볼 수 있는 사용자(`active`)에게, 판의 review.sources와 SHA가 일치하는 생성 보존본 PDF만 흘려 보낸다. 단일 `Range`(206/416), `Accept-Ranges`, `ETag`=SHA, `Cache-Control: private, max-age=3600`. 쓰기·사건 없음. `?sha=`는 캐시 구분용이며 서버 판단에 쓰지 않는다.
- `storage.open_stream(byte_range=)`: R2 `get_object(Range=)`/로컬 seek. 덱 모아받기와 같은 우회 사정이다.
- `evidence.attach_evidence`: 슬라이드마다 `proxyPath` 추가. `url`(원본 열기 링크)은 그대로.
- CORS: `Range` 요청 헤더 허용, `Accept-Ranges/Content-Range/Content-Length` 노출. 이것이 없으면 PDF.js가 교차 출처에서 범위 요청을 못 해 22.7MB 전체를 받는다.
- 웹 `RootPdfSlides`: `proxyPath`가 있으면 API 주소 + 로그인 헤더로 PDF.js에 넘긴다. 실패한 문서 로딩은 캐시에 남기지 않는다. 옛 응답(proxyPath 없음)은 종전 URL을 쓴다.

## 개념지도
공개 판 261104_02의 실제 구조(주제 개념 C### 11개 이름, 문항별 답 개념 N*_A, 관계는 C###→N*_A association, parent_ids 없음)를 그대로 트리로 만든다(`rootMapTree.ts`).
- 문항(target)은 자기 개념 중 가장 많은 문항이 공유하는 개념(=주제) 밑에 붙는다. 답 개념은 노드가 되지 않는다(답 노출 방지). 같은 부모 아래 같은 이름의 개념(C001/C002)은 한 노드. 명시적 parent_ids가 있으면 그대로 중첩(순환 방지). 개념이 없는 문항은 "기타".
- 순서: 근거 쪽 번호(강의 순서), 없으면 원래 순서.
- 화면(`RootMap.tsx`): 좌→우 트리(곡선 연결), 끌기 이동·휠/핀치·＋/－·전체·현재 문제·모두 펼치기/접기·크게 보기, 키 +/−/0/Esc. 주제 클릭=펼침/접기와 그 문항으로 이동(읽을 수 있는 최소 배율 0.8 유지). 확대(≥1.15)하면 문항에 상태·쪽이 더 보인다. 옆 패널(모바일은 아래): 주제=상태별 개수·하위 문항 목록, 문항=쪽·상태·현재 문제·답 범위(접힘)·중요도 근거. 검색은 주제/문항 텍스트. 접근성용 "목록으로 보기". 자료 범위·출제포인트 접기는 유지. 표시용으로 문항 제목의 `**`만 지운다.
- 지도 API·지도 열람 기록(mapSeen/도움 표시)은 바꾸지 않았다.

## 확인
- 실제 판(로컬 보존본 curated-result.json + S1.pdf, SHA 4b4229bc…)을 격리 SQLite/로컬 저장소에 올린 `serve_real_fixture.py`로 확인: 답 공개 → PDF 3쪽 렌더링(200 후 206 범위 요청), 지도 11주제·98문항, 주제 펼침·검색 이동·확대 상세·모바일 375px(가로 넘침 없음).
- 운영과 같은 교차 출처 조건(웹 5199 → API 8037, Authorization 헤더): OPTIONS 200 → 206 범위 요청 → 렌더링, 콘솔 오류 없음.
- 운영 DB·R2·학습 기록에 쓰지 않았다. 문항·은행·공개 범위 변경 없음.
