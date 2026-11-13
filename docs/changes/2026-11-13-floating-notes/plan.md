# 자유 노트 플로팅·강의명·로컬 사진 — 구현 계획

## 변경 범위·대상 파일·순서
1. 서버: `server/app/routes/notes.py`(image 블록·id 검증), `server/tests/test_notes.py`(image 저장·html 버림·잘못된 id 422).
2. 웹 공용: `web/src/types/notes.ts`(image 블록), `web/src/notes/useNoteStore.ts`(새: NotesPage의 목록·불러오기·지연 저장·flush를 훅으로 꺼냄) → `NotesPage.tsx`가 이 훅을 쓰게(동작 동일).
3. 사진: `web/src/notes/localImages.ts`(새: IndexedDB 저장·읽기·지우기, 축소), `NoteEditor.tsx`(image 블록 그리기·붙여넣기·끌어놓기·`/사진`), `notes.css`.
4. 플로팅: `web/src/notes/FloatingNotes.tsx`(새), `web/src/notes/noteLecture.ts`(새: 강의명 context·`useNoteLecture`), `web/src/App.tsx`(셸에 Provider·`<FloatingNotes/>` 한 곳), `notes.css`(창·버튼).
5. 강의명 알림 한 줄씩: `web/src/lecture/QuizPage.tsx`, `web/src/bank/RootLearning.tsx`, `web/src/bank/BankStudy.tsx`.
- 건드리지 않음: RootSolve.tsx(선지 접기 세션), GuidePage.tsx, Sidebar(「자유 노트」 메뉴는 유지).

## 검사 명령과 성공 조건
- `server/.venv/Scripts/python.exe -m tests test_notes`(격리 로컬 sqlite, 운영 DB 미사용).
- `npm --prefix web run typecheck`, `npm --prefix web run build`.
- 로컬 미리보기에서 브라우저로 확인: 버튼·창 열고 닫기, 퀴즈 화면에서 강의명 넣기, 창에서 숫자·V 입력 시 퀴즈 반응 없음, 사진 붙여넣기 → 새로고침 후 유지, 요청 본문에 이미지 바이트 없음(네트워크 확인), 휴대폰 폭·어두운 화면.
- PR CI `Tests and build`.

## 위험·복원·승인할 범위
- 위험: 플로팅 버튼이 풀이 화면 하단 버튼을 가림 / 노트 창 키 입력이 퀴즈로 샘 / 사진은 기기에만 있어 사용자가 잃을 수 있음(요구된 한계).
- 복원: PR revert. DB 변경 없음.
- 승인 요청 범위: 위 파일의 로컬 구현·검사·PR 생성까지. master 병합(=운영 자동 배포)은 별도 확인.
