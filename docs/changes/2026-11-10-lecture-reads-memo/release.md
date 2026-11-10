# 강의록 회독 기록과 강의별 짧은 메모 — 배포 준비

## 코드 리뷰·검증 결과
- 서버 lecture_notes·route_contract·usage 통과, web typecheck·build 통과, 고정물 브라우저 확인(아래 state.json 기록).

## 배포 대상 버전·순서·데이터 변경
1. (2026-11-10 승인) 운영 DB에 `note_read`, `lecture_memo` 생성 + RLS — `create_tables.py`(세 표만 create_all).
   같은 스크립트가 자유 노트의 `user_note`도 없으면 만든다(운영에 없을 가능성, claude/error-cors 조사). 자격 정보는 사용자가 넣고 실행한다.
2. (승인 필요) master 병합 → API 자동 배포 → 같은 SHA로 Pages.

## 배포 후 확인·롤백·필요한 사람 승인
- 패널에서 + / 지우기 / 되돌리기, 메모 저장 후 새로고침 유지, 칸 회독 줄 반영, 다른 계정에 안 보임.
- 롤백: PR revert(표는 유지).
