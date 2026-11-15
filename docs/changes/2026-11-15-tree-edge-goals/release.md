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
- PR D(`feat/tree-edge-backfill`, PR A 위에 쌓음): 구현·검사 완료. 콜레라 편 로컬 사본 실측 결과는 아래에 적는다.

## 복원

PR revert로 되돌린다. presuppose/1은 새 ledger에만 기록된다. 이전 실행의 이어 가기와 공개된 판은 영향이 없다.

## 실측 — 콜레라·캄필로박터·수도모나스(261110_01 공개판 auto-de7da04c…, 229문항), 로컬 사본, 운영 쓰기 없음

| 항목 | 1차(프롬프트 수정 전, 중복 포인트 합침 후) | 2차(존재 목표 프롬프트·출제 표시 수정 후) |
|---|---|---|
| 발문이 전제로 준 연결 | 126 | 117 |
| 그중 이미 답으로 묻는 연결 | 70 | 66 |
| 존재 포인트 → 존재 목표 | 39 → 34 | 29 → 25 |
| 추가 출제(1회차 / 2회차) | 26목표 중 12문항 / 23목표 중 2문항 | 24목표 중 22문항 / 8목표 중 7문항 |
| 새 문항 · 그중 존재 목표에 놓인 것 | 14 · 일부 | 29 · 26 |
| 과제 | 224 → 236 | 224 → 253 |
| 선행 연결 | 52 | 63 |
| 끝내 답으로 묻지 않은 전제 | 47 | 16 |
| 기존 문항·검토·의학 판정 | 그대로(결과 계약 통과) | 그대로(결과 계약 통과) |

- **1차의 문제와 수정.**
  - 정규화가 존재 목표를 「주요 독력인자와 기능은?」 같은 복합 목표로 만들었다. 그래서 출제가 기능 문항을 쓰거나 목표를 건너뛰었다.
  - 이를 고쳐 포인트·목표를 「A의 (범주): 이름」으로 고정했다. 출제 입력에는 `existence` 표시(전제로 쓰는 발문)를 준다.
- **2차에서 나온 존재 문항 예.**
  - 「P. aeruginosa의 주요 조직 손상 효소…」 → LasA; LasB; Phospholipase C
  - 「대표 항녹농균 항균제의 계열」 → β-lactam; Fluoroquinolone; Carbapenem
  - 「H. pylori의 주요 병원성 인자」, 「P. aeruginosa가 일으키는 대표 임상 감염 양상」
  - 「C. jejuni 감염의 주된 임상 질환 범주」 → 급성 장염; 장관외감염
- **2차에 남은 것.**
  - 이미 다른 문항이 원소 일부를 묻는 목표에서 「…를 제외한 다섯 가지는?」 식 발문이 나온다. 출제 입력이 빠진 component만 주기 때문이다.
  - 존재 문항 일부가 문항 검토가 고른 기존 관계를 따라 기존 목표에 놓인다(예: C. jejuni 질환 문항 → D049). 선행 순서는 그 목표 기준으로 붙는다.
  - 「콜레라에 쓰는 대표 항균제」 목표에는 문항이 써지지 않았다.
  - 기전·기능에 가까운 목표가 몇 개 섞였다(Exotoxin A의 화학적 작용 등).
