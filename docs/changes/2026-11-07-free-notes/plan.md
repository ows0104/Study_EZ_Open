# 자유 노트 — 구현 계획

## 변경 범위·대상 파일·순서
1. 서버: `server/app/models/notes.py`(UserNote+RLS), `models/__init__.py` 등록, `server/app/routes/notes.py`(5개 경로), `server/app/main.py` 라우터 등록.
2. 서버 검사: `server/tests/test_notes.py`(생성·목록 순서·수정·삭제·태그 정리·제한·계정 격리·미승인 403·미로그인 401), `server/tests/test_route_contract.py` 경로 추가.
3. 웹: `web/src/notes/NoteEditor.tsx`(프로토타입 편집기 이식, 「강의」→「태그」, 붙여넣기·HTML 정리), `web/src/notes/NotesPage.tsx`(서버 목록·자동 저장·삭제),
   `web/src/notes/notes.css`(프로토타입 `notes-*`/`nb-*` 스타일 이식), `web/src/types/notes.ts`, `web/src/App.tsx` 경로 `/notes`,
   `web/src/shell/Sidebar.tsx` 메뉴(아이콘 `note`).
4. 문서: `docs/map.md` 한 줄, `web/CLAUDE.md` 수정 위치 한 줄, 이용방법(`GuidePage.tsx`)에 자유 노트 짧은 항목.

## 검사 명령과 성공 조건
- server: `server/.venv/Scripts/python.exe -m tests notes`, `-m tests route_contract` 통과(격리 sqlite).
- web: `web`에서 `npm run typecheck`, `npm run build` 통과.
- 로컬 실행 확인: 격리 로컬 DB로 서버+웹을 띄워 노트 생성·md·색·태그·새로고침 후 유지·삭제를 브라우저로 확인.

## 위험·복원·승인할 범위
- 승인 요청 범위: 위 파일의 로컬 구현·검사·브랜치 커밋/PR까지. 운영 DB 표 생성과 master 병합(=자동 배포)은 별도 중요 승인.
- 위험: 새 표가 운영 DB에 없을 때 API가 먼저 배포되면 `/notes`만 500. 다른 화면 영향 없음. 복원은 PR revert(표는 남겨도 무해).
- contentEditable HTML은 본인에게만 보이며 그릴 때 허용 목록으로 정리한다.
