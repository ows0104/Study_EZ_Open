# Main-Quiz 관리자 출제 기본값을 새 구조 2로 — 배포 준비

## 코드 리뷰·검증 결과
- diff는 2개 파일이다: `RootGenerationPanel.tsx` +8/−5, 테스트.
- API·서버·생성기·러너 코드는 변경하지 않았다.
- 패널 테스트 12/12 통과(새 검사 2개 포함), typecheck 통과, `npm run build` 통과.
- `web/tests/main-quiz-render.test.cjs`는 이 변경과 무관하게 실패한다. `api.ts`·`RootPdfSlides.tsx`의 `import.meta`를 CommonJS로 읽다가 SyntaxError가 난다. 이 테스트는 CI에서 돌지 않으며, 이번 작업에서 고치지 않았다.

## 배포 대상 버전·순서·데이터 변경
- master 병합으로 Pages가 자동 배포된다. API 코드는 바뀌지 않는다.
- DB·운영 데이터 변경은 없다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 배포된 Pages의 RootGenerationPanel 청크에 「새 구조 2 (기본)」 문구가 있는지 본다.
- 롤백: revert한 뒤 다시 병합한다.
- 추가 사람 승인: 필요 없다. 화면 기본값만 바뀌고, 강의별 출제·공개는 여전히 관리자의 버튼 클릭이 승인이다.
