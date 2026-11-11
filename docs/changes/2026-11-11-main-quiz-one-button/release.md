# Main-Quiz 관리자 출제를 버튼 하나로 — 배포 준비

## 코드 리뷰·검증 결과
- 화면: `RootGenerationPanel.tsx`에서 구조 Mode·입력 상태·파일 업로드·「설정·기존 지도 사용」 접기를 지웠다. 새 요청은 `NEW_REQUEST`
  (map-tree/3·source·cli·병렬 아님·빈 입력·examDate null) + 체크박스의 `privatePilot` + 새 requestId다.
  이어 하기는 원래 요청을 그대로 보내고(map-tree 요청은 이유 필요), 같은 공개 범위를 적는다.
- `roots.css` 한 줄(버튼·체크박스 한 줄 배치, 호출 상한 작은 글씨), `GuidePage.tsx` 관리자 출제 문단을 지금 동작으로 고쳤다.
- API·서버·생성기·러너 코드는 변경하지 않았다. 서버 `RequestIn`은 지금 보내는 본문을 그대로 받는다(map-tree/3는 source·cli·병렬 아님 조건 충족).
- 검사: 패널 테스트 9/9 통과(정확한 본문, 체크박스 비공개, 이전 판을 끌어오지 않음, 이어 하기의 원래 공개 범위 포함),
  `npm run typecheck`·`npm run build` 통과.
- 로컬 미리보기(가짜 API)에서 데스크톱·390px 화면 확인, 390px 가로 넘침 없음. 체크 후 누르면 실제 브라우저도
  `pipeline: map-tree/3, privatePilot: true`를 보냈다.
- 실행하지 않은 검사: `web/tests/root-generation.test.cjs`·`main-quiz-generation-browser.test.cjs`는 Playwright가 필요한데 이 환경에 없다.
  없어진 설정 대신 체크박스·새 본문으로 고쳐 두었지만 돌려 보지 않았다. 둘 다 CI에서 돌지 않는다.
  root-generation.test.cjs의 뒷부분(합성 서버가 map-tree/3를 처리해 게시까지 가는지)은 이번 변경 전에도 병렬 요청 기준이라 맞는지 확인하지 못했다.
- `web/tests/bank-links.test.cjs`는 5개가 이 변경과 무관하게 실패한다(이 패널을 모의 객체로 바꿔 끼우는 테스트). CI 밖이며 고치지 않았다.

## 배포 대상 버전·순서·데이터 변경
- master 병합으로 Pages가 자동 배포된다. API 코드는 바뀌지 않는다.
- DB·운영 데이터 변경은 없다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 배포된 Pages의 RootGenerationPanel이 든 청크에 「학생 비공개 (내 계정에서만 확인)」이 있고 「설정·기존 지도 사용」이 없는지 본다.
- 롤백: revert한 뒤 다시 병합한다.
- 추가 사람 승인: 필요 없다. 기본 공개 범위(학생 공개)는 이전과 같고, 강의별 출제·공개는 여전히 관리자의 버튼 클릭이 승인이다.
