# 족보 풀이 플로팅 노트 강의명 버튼 — 구현 계획

## 변경 범위·대상 파일·순서
1. `web/src/jokbo/JokboPage.tsx`: `useNoteLecture` import 1줄, 문서 불러오기 effect 뒤 호출 1줄.

## 검사 명령과 성공 조건
- `npm --prefix web run build`(tsc 포함).
- 로컬 미리보기(격리 API·sqlite)에서 족보 화면 노트 창에 「＋강의명」 표시·커서 자리 삽입 확인.
- PR CI `Tests and build`.

## 위험·복원·승인할 범위
- 위험 낮음(표시 알림만). 복원: PR revert.
- 승인 범위: 위 파일 구현·검사·PR·병합(사용자 「Go ahead」, 앞선 같은 흐름에서 「Merge it」).
