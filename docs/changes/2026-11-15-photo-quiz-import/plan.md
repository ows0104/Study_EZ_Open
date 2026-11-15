# 사진 실습 Main-Quiz 수작업 반입 — Implementation Plan

[Spec](spec.md). 사용자의 작업 요청이 구현 승인이다. 운영 DB 쓰기(반입)·학생 공개는 따로 묻는다.

## 변경 파일

| 파일 | 변경 |
|---|---|
| `studyez_contracts/roots/media.py` | `photo=` 모드(JPEG·200장·24 MB·64M 화소), `jpeg_size`, `photo_import(doc)`, 공개 URL의 실제 형식 |
| `studyez_contracts/roots/validate.py` | 문서 그림 검사에 `photo=photo_import(doc)` |
| `server/app/root_learning/content.py` | 학생 앞면 allowlist에 `clue` |
| `web/src/types/bank.ts`, `web/src/bank/RootSolve.tsx`, `web/src/bank/main-quiz.css` | 「힌트 보기」 버튼·`H` |
| `web/src/notices/GuidePage.tsx` | 단축키 안내 한 줄 |
| `web/src/bank/RootLearning.tsx` | 관리자 업로드 상한 30 MB (별도 커밋 — claude/map-button과 같은 파일, 다른 줄) |
| `scripts/photo_quiz_import.py` | 수작업 사진 문항 → `roots/1` 문서 조립·검사 |
| `tests/contracts/test_photo_media.py`, `server/tests/test_root_photo_import.py` | 검사 |

## 순서

1. 계약(media·validate) → 계약 검사.
2. 서버 allowlist → 서버 Main-Quiz 검사(`-m tests root`).
3. 웹 → `npm run typecheck`, 로컬 fixture(격리 sqlite)에 실제 문서를 게시해 브라우저로 힌트·JPEG 확인.
4. 조립 도구로 실제 문서 생성·`validate_document` 통과, 로컬 서버에서 등록·게시·풀이.
5. Draft PR → CI → 병합(코드 배포, 되돌릴 수 있음).
6. 운영 반입은 사용자 확인 뒤: 관리자 화면에서 JSON 업로드 → 「나만」 활성화 → 사용자 확인 → 학생 공개 여부를 따로 묻는다.

## 복원

- 코드: PR revert. 기존 판(PNG)은 검사 결과가 같다.
- 반입 판: 관리자 화면에서 비활성화(기록 보존). 판 삭제는 하지 않는다.

## 검사 기록 (2026-11-15, 로컬)

- `tests/contracts` 415 통과(새 5개 포함).
- 서버 `-m tests root` 45개 통과(새 `test_root_photo_import` 포함). `root_map_tree`·`root_map_tree_v3` 두 개는 서버 venv에
  pymupdf가 없어 처음엔 import 실패 → pymupdf를 경로에 더해 다시 돌려 통과(코드 원인 아님).
- 웹 `npm run typecheck` 통과. `tests/main-quiz-render.test.cjs`는 `import.meta` 오류로 실패하는데 변경 전 HEAD에서도
  똑같이 실패한다(기존 결함, 이 작업과 무관). 로컬 fixture에서 86문항 판: 학생 비공개(「나만」)·관리자 열림, 첫 문항 JPEG 820×736,
  「힌트 보기」/`H`로 펴고 접힘, 답 보기·평가 정상.
- 실제 문서: 86과제, 그림 참조 145(고유 137장, 9.85 MB), JSON 14.9 MB, `validate_document` 통과.
