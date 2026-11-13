# 개인 대화 ▾ 「링크 수정」 — 구현 계획

## 변경 범위·대상 파일·순서
- `web/src/calendar/MyLinkEditor.tsx`(새): 개인 링크 편집칸.
- `web/src/calendar/ChatSplit.tsx`: `onLink`·`linkOpen` 메뉴 항목.
- `web/src/calendar/PreviewAction.tsx`, `ReviewAction.tsx`: 연결.
- `web/tests/review-actions.tsx`: 고정물이 PUT 본문을 보이게.

## 검사 명령과 성공 조건
- `npm --prefix web run typecheck`, `npm --prefix web run build`, PR CI.
- 고정물(`/tests/review-actions.html`)에서 메뉴 항목·미리 채운 값·PUT 경로/본문 확인. 운영 DB 미사용.

## 위험·복원·승인할 범위
- 웹만. 복원은 PR revert. master 병합(=운영 배포)은 사용자 확인 후.
