# Main-Quiz 풀이 지연 제거 — 배포 준비

## 코드 리뷰·검증 결과
- 서버 전체 `python -m tests` 124/124 통과(격리 SQLite, `PYTHONPATH`=이 worktree — 빌려 쓴 venv가 옛 checkout의
  `studyez_contracts`를 읽어 12개가 import 오류로 실패한 첫 실행은 환경 문제였다). 신규 `test_root_prepare` 통과.
- `check_root_learning.py --check root-ui` 4/4 통과: 기존 3개(재시도·충돌 보존·다른 탭·Z·지도·PDF 실패·저장소 차단)와
  신규 1개(저장 1.5 s 지연에서 답·다음 문항 각 1 s 안, 동작 사이 세션 GET 0회, 모든 PDF 요청이 `bytes=a-b` 범위).
- `tsc --noEmit`, `npm run build` 통과. `git diff --check` 통과.
- 리뷰에서 고친 것: 마지막 평가 뒤 서버 요약 읽기가 빠른 Z보다 늦게 와 새 화면을 덮을 수 있었다 → 버전이 같을 때만 적용.
- 남은 위험: 화면이 서버보다 앞서 있다가 409로 되돌아가는 경우(다른 탭·문항 준비 상태 변화). 보존·다시 불러오기로 복구.

## 배포 대상 버전·순서·데이터 변경
- master 병합 → GitHub 검사 → API 자동 배포 → Pages가 같은 SHA의 API를 확인한 뒤 웹 배포.
- 새 경로는 API에만 있고 옛 웹은 부르지 않는다. 새 웹이 옛 API를 만나면 미리 받기가 404 → 예전 경로로 동작.
- DB 스키마·데이터 변경 없음.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: `/api/health` revision, openapi에 `…/prepare`, 배포된 웹 청크에 `prepare?start=`. 운영 로그에서 실제 풀이 구간에
  `…/events` 사이의 `GET /sessions/{id}`가 사라지고 `sources/`가 206만 남는지.
- 롤백: git revert 후 master, 또는 이전 Cloud Run revision·Pages 배포.
- 사람 승인: 「사람에게 묻는 것」에 닿지 않는다(코드만, 되돌릴 수 있음). 근거는 intent.md의 사용자 요청 원문.
