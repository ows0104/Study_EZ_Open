# Main-Quiz 개인 수정 형식 — 배포 준비

## 검증 결과
- 새 서버 검사 `server/tests/test_root_personal_format.py` 통과(격리 SQLite): 여섯 형식 저장·형식별 422·같은 형식은 글만·다른 계정 원형·되돌리기·연결 판 409.
- `-m tests root main_quiz bank_personal personal route_contract recall_choices mcq_choices`: 51개 중 49개 통과.
  `test_root_map_tree`·`test_root_map_tree_v3`는 로컬 venv에 pymupdf가 없어 import에서 멈춤(변경과 무관, CI에서 확인).
- 웹 `tsc -b --noEmit` 통과. 고정물 `web/tests/root-edit-format.html` 11개 확인 통과(가짜 API).

## 배포 순서·데이터 변경
1. 운영 DB `init-db` — `bank_personal_edit.structure JSON` 칼럼 추가(NULL, 기존 행 그대로). **API 배포 전에 먼저.**
2. master 병합 → API·웹 자동 배포.
둘 다 사람 승인. 칼럼 없이 API가 먼저 뜨면 개인 수정 조회가 깨진다.

## 배포 후 확인·롤백
수정창에서 주관식 문항을 빈칸으로 바꿔 저장 → 풀이에서 빈칸·답 채움 확인, 되돌리기 확인. 롤백은 커밋 revert(칼럼은 남아도 무해).
