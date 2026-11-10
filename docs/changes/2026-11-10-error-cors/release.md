# 서버 500에도 CORS 헤더 — 배포 준비

## 코드 리뷰·검증 결과

| 검사 | 결과 |
|---|---|
| `server -m tests error_cors` | 통과 |
| 서버 전체(`scripts/check_server_release.py`, 격리 sqlite·로컬 저장소) | 131/133 통과. 실패 2개 `test_root_map_tree`·`test_root_map_tree_v3`는 로컬 venv에 PyMuPDF(`fitz`)가 없어서다(변경과 무관, 다른 PR도 같은 2개). CI에서 돈다 |

- `test_error_cors`가 확인하는 것: 표 없는 `/api/me/notes` 500에 허용 출처 헤더·`Vary: Origin`이 붙음, 본문은 `{"detail": "Internal Server Error"}`(예외 내용 없음),
  허용 안 된 출처·Origin 없는 요청엔 헤더 없음, `/api/health` 200·401 응답 헤더는 그대로, 예외는 다시 던져져 로그에 남음.
- 수정 전 코드로 같은 상황을 재현하면 500에 `Access-Control-Allow-Origin`이 없었다(조사 중 로컬 재현).
- 남은 위험: 응답을 보내기 시작한 뒤(스트리밍 중)의 예외는 그대로 둔다. 헤더를 바꿀 수 없다.

## 배포 대상 버전·순서·데이터 변경

- DB·저장소·웹 변경 없음. master 병합 = API 자동 배포.
- 이 변경은 「Failed to fetch」를 실제 500으로 보이게 할 뿐이다. 자유 노트가 열리려면 운영 DB `user_note` 표 생성(`init-db`)이 따로 필요하다.

## 배포 후 확인·롤백·필요한 사람 승인

- 필요 승인: master 병합(=운영 배포).
- 확인: `/api/health` revision, 정상 화면들이 그대로 열리는지.
- 롤백: PR revert.
