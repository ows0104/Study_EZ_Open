# Main-Quiz: 세부를 묻기 전에 상위 연결의 존재를 묻는다 — 출시 기록

## 변경 (PR 셋, 각자 혼자 검사 통과)

- **PR A `feat/tree-edge-goals`**: 새 출제 경로(spec R1·R2 간선·R3·R4·R5).
  - 새 정책 presuppose/1은 새 ledger만 적용한다.
  - `v4-presuppose-<k>`는 발문이 사실로 준 상위 연결과, 그 연결을 답으로 묻는 문항을 판정한다.
  - 아무도 묻지 않는 연결은 존재 목표가 된다. `v4-supplement-normalize-presuppose`만 새 association을 더할 수 있다.
  - 조립이 판정 기록에서 선행 연결(`PRE-…`)을 결정적으로 만든다.
  - 프롬프트: `v4/presuppose.md`·`supplement-normalize-presuppose.md`(새), `normalize`·`add`·`fix`·`item-review`.
  - 측정: `python -m quizbank.presuppose_report`.
- **PR B `feat/tree-edge-map`**: 지도 화면이 `prerequisite` 관계를 가로 연결·답 노드 판정에서 뺀다.
  공개된 판에는 이 관계가 0개라 기존 지도는 바뀌지 않는다.
- **PR C `feat/tree-edge-planner`**: 학습 계획의 선행 끌어오기.
  - 존재 목표를 배웠어도 최근 평가가 모두 independent가 아니면, 세부 목표 앞에 끌어온다.
  - 중요도 필터 밖이어도 끌어온다. 오늘 이미 푼 것은 다시 끌어오지 않는다.
  - 공개된 판에는 선행 연결이 0개라 지금 동작은 바뀌지 않는다.

## 검사 (2026-11-15)

- **PR A**
  - 루트 `python -m pytest tests`: 3008 통과. 실패 1은 `test_desktop_control` 한글 바로가기(알려진 환경 실패)다.
  - 새 `tests/quizbank/test_presuppose.py` 8개
    - 끝까지 도는 경우: 존재 목표 생성 → 과제 → 선행 간선 → 과제 순서
    - 이미 묻는 연결
    - 옛 ledger
    - 출력 검사, 간선 규칙, 관계 제한, 러너 매핑, 측정 도구
  - 단계 순서를 고정한 `test_pipeline_resilience` 기대값에 `v4-presuppose-0`을 넣었다(의도된 변경).
- **PR B**: `web/tests/main-quiz-map-tree.test.cjs` 6개 통과. 새 1개는 옛 코드에서 실패한다.
  `tsc -b --noEmit`에서 내 파일은 오류가 없다. 남은 오류는 `RootPdfSlides.tsx`의 `pdfjs-dist`이며, 메인 체크아웃 node_modules가 옛것이라서다.
- **PR C**: 서버 `python -m tests root`에서 46개 중 44개 통과(새 `test_root_prereq_release` 포함).
  실패 2(`test_root_map_tree`·`test_root_map_tree_v3`)는 서버 venv에 pymupdf가 없어서다(알려진 환경 실패).

## 아직 안 한 것 (따로 승인)

- 실측: 과목 성격이 다른 3편을 로컬에서 새로 출제해 R5 수치를 확인한다. 모델 호출이 많고 러너 PC 시간을 쓴다.
- 병합: master 병합은 API·웹을 자동 배포한다. 병합 뒤 러너 재설치가 필요하다(PR A는 러너가 읽는 코드다).
- PR D: 공개 강의 보강 경로. PR A 병합 뒤 시작한다.

## 복원

PR revert로 되돌린다. presuppose/1은 새 ledger에만 기록된다. 이전 실행의 이어 가기와 공개된 판은 영향이 없다.
