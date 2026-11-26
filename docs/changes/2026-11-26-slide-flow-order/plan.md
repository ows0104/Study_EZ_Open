# 오늘 학습 첫 순서를 슬라이드 흐름으로 — 구현 계획

승인: 사용자 2026-11-26 「첫 학습 순서를 합의대로 고칠까요?」에 「순서부터 정하자」, 비교표 뒤 「슬라이드 흐름으로」, 중요도 「오늘 범위 고르기에만」.
범위: 로컬 구현·검사·Draft PR. Ready·병합(=API 배포)은 따로 묻는다.

## 변경 범위·대상 파일·순서

1. `server/app/root_learning/planning.py`
   - `task_pages`, `slide_flow`(R1~R3) 추가. `plan_tasks`의 목표 단위 emit + `spread_directions`를 `slide_flow`로 바꾼다.
   - `links`가 있으면 `order_plan`에 존재 간선을 뺀 문서 사본을 넘긴다(R2).
   - `plan_tasks`의 `priority`에 구조 근거(R4).
2. `server/tests/test_root_slide_flow.py` 새 검사.
3. 이 폴더의 intent·spec·plan.

## 검사 명령과 성공 조건

- `server/.venv/Scripts/python.exe -m tests`(PYTHONPATH=..) 전부. 이 PC에서 pymupdf가 없는 두 파일(test_root_map_tree, test_root_map_tree_v3)은 import 단계에서 멈춘다 — 이 변경이 건드리지 않는 모듈(fitz·pymupdf)이다.
- 피부근염 로컬 판(`runs/_root-generation/aadee987…/generation/result.json`)으로 계획을 다시 계산해 spec 수용 기준을 센다.

## 위험·복원·승인할 범위

- 모든 공개 Main-Quiz 강의의 오늘 학습 순서가 바뀐다(기록 영향 없음). 병합이 곧 API 배포라 Ready·병합은 따로 묻는다.
- 같은 방향 과제를 회차 전체에 흩던 동작이 사라진다. 같은 쪽 안에서만 떼어 놓는다.
- 복원: revert.
