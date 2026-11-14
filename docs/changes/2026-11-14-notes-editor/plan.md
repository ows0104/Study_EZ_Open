# 자유 노트 편집기 보완(들여쓰기·표·붙여넣기·토글) — 구현 계획

## 변경 범위·대상 파일·순서
1. 서버: `server/app/routes/notes.py`(indent·toggle·table 필드), `server/tests/test_notes.py`.
2. 웹 타입·저장: `web/src/types/notes.ts`, `web/src/notes/useNoteStore.ts`(toInput에 새 필드).
3. 편집기: `web/src/notes/NoteEditor.tsx`(들여쓰기·토글·복제·이동·실행 취소·붙여넣기), 새
   `web/src/notes/blockTree.ts`(하위 범위·번호·붙여넣기 해석 순수 함수), 새 `web/src/notes/NoteTable.tsx`(표 블록).
4. 모양: `web/src/notes/notes.css`(줄간격·들여쓰기·표·토글·회색 칸).
5. 이용방법: `web/src/notices/GuidePage.tsx`에 노트 단축키 안내가 있으면 맞춘다.
- 건드리지 않음: FloatingNotePanel·FloatingNotes(편집기를 그대로 씀), 사진 저장 방식.

## 검사 명령과 성공 조건
- `server/.venv/Scripts/python.exe -m tests test_notes`(격리 로컬 sqlite, 운영 DB 미사용).
- `npm --prefix web run typecheck`, `npm --prefix web run build`.
- 로컬 미리보기에서 브라우저로 확인: Tab/Shift+Tab, 번호 단계, 표 만들기·편집·저장 후 새로고침,
  여러 줄·TSV 붙여넣기, 하단 회색 칸 없음, 토글 접기, Ctrl+D·Ctrl+Shift+↑↓·Ctrl+Z, 플로팅 창, 어두운 화면.
- PR CI `Tests and build`.

## 위험·복원·승인할 범위
- 위험: 실행 취소가 블록을 다시 그려 커서가 튈 수 있음 / 이전 웹 저장 시 새 필드 손실(배포 사이 짧은 구간).
- 복원: PR revert. DB 변경 없음.
- 승인 범위: 위 파일의 로컬 구현·검사·PR 생성. master 병합(운영 자동 배포)은 별도 확인.
