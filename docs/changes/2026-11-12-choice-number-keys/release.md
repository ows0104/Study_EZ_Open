# 복습 퀴즈 객관식 선지 번호 표시와 1–4 키 선택 · 5 키 제외 — 배포 준비

## 코드 리뷰·검증 결과

- 서버 `python -m tests root_exclude`: 통과(제외 → 다음 과제, 같은 문항 뒤 과제 건너뜀, 오늘 계획에서 빠짐, Z로 복구, 같은 요청 ID 멱등, 과제 없을 때 409).
- 서버 `python -m tests root`: 37개 중 35개 통과. 실패 2개(test_root_map_tree, test_root_map_tree_v3)는 검사에 쓴 가상환경에
  `pymupdf`·`pytest`가 없어 import 단계에서 멈춘 것 — 이번 변경과 무관, 이 환경에서 미실행으로 본다. CI에서 확인 필요.
  (이 worktree에 server/.venv가 없어 다른 worktree의 venv를 PYTHONPATH=이 worktree로 빌려 실행.)
- 웹 `npm run typecheck`: 통과. `node --test tests/answerPoints.test.cjs tests/answer-readable.test.cjs`: 45개 통과.
- 브라우저(로컬 vite 고정물, 서버·DB 없음): `tests/root-choice-keys.html` ALL PASSED, `tests/choice-explanations.html` ALL PASSED.
  `tests/bank-interactions.test.cjs`(Playwright)는 로컬에 playwright 모듈이 없어 미실행. CI 워크플로도 이 파일을 돌리지 않는다.
- 미실행: 실제 운영 데이터의 해설 본문 글자 언급 확인, RootLearning의 제외 → Z 전체 흐름 브라우저 확인(서버 검사와 단위 픽스처로만 확인).

## 배포 대상 버전·순서·데이터 변경

- master 병합 시 API → 웹 자동 배포. DB 스키마 변경 없음. 새 RootEvent kind 'exclude'만 쌓인다.
- 웹이 먼저 나가고 API가 옛 판이면 'exclude' 요청이 422로 거절된다 — 기존 순서(API 먼저)를 따른다.

## 배포 후 확인·롤백·필요한 사람 승인

- 확인: 내 계정 Main-Quiz 객관식에서 번호 머리표, 1–4 선택, 5 제외 뒤 다음 문제, Z 복구.
- 롤백: 커밋 되돌리기. 'exclude' 이벤트는 남고 옛 코드는 무시하므로 제외했던 문항이 다시 나온다.
- master 병합(=운영 배포)은 사용자 승인 필요.
