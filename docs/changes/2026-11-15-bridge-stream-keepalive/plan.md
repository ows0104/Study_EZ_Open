# 브리지 다운로드 유지 — 구현 계획

승인: 사용자 「승인, 진행」(2026-11-15). master 병합(=자동 배포)은 별도 승인.
확장은 배포 파이프라인이 아니라 관리자가 폴더를 다시 로드해야 반영된다. 스토어판은 별도 제출.

## 파일

1. `bridge/background.js`: 포트별로 조각을 약 1MB로 묶어 보내고 `FILE_ACK`를 기다린다(60초 넘으면 중단).
   탭이 포트를 끊으면 R2 읽기를 취소한다.
2. `bridge/chatgpt-bridge.js` `fetchFile`: 조각마다 `FILE_ACK`, 끊기면 한 번 재시도, 무응답 시한 120초,
   실패 문구에 파일명·받은 MB·시도 횟수.
3. `tests/bridge/test_file_stream.cjs`(+ `.py` 진입점이 필요하면): 가짜 chrome으로 배경·탭을 이어 정상·끊김 1회·
   끊김 2회·ACK 대기를 검사.

## 검사

- `node --test tests/bridge/*.cjs`, `python -m pytest tests/bridge`.

## 위험·복원

- 배경과 탭이 같은 확장에 함께 실리므로 판 섞임 없음. 복원은 `git revert`.

## 검사 결과 (2026-11-15)

- `node --test tests/bridge/*.cjs`: 117개 통과(새 `test_file_stream.cjs` 4개 포함: 1MB 묶음·ACK 하나씩, 끊김 1회 재시도
  성공, 끊김 2회 정지 문구, 사용자 중지 시 재시도 없음·R2 읽기 취소).
  `test_web_versions.cjs`는 새 worktree에 `web/node_modules`가 없어 처음 실패, 메인 폴더 모듈을 잠시 연결해 8개 통과.
- `python -m pytest tests/bridge`: 9개 통과.
- 실제 Chrome에서 큰 PDF로 확인은 아직. 관리자가 Profile 1 확장을 이 코드로 다시 로드한 뒤 확인한다.
