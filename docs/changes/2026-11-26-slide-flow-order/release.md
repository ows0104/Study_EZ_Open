# 오늘 학습 첫 순서를 슬라이드 흐름으로 — 배포 준비

## 코드 리뷰·검증 결과

- `server/.venv/Scripts/python.exe -m tests`(PYTHONPATH=..): 170개 중 168개 통과.
  실패 2개(test_root_map_tree, test_root_map_tree_v3)는 이 PC의 server venv에 pymupdf·fitz가 없어 import 단계에서 멈춘 것이다. 바뀐 파일과 무관하다.
- 새 검사 `server/tests/test_root_slide_flow.py` 통과.
- 피부근염 로컬 판(시험일 11-27, Must-Know~Important, 선행 포함) 재계산: 68과제, 「IIM의 세 가지 범주」 2번째, 첫 다섯 문항 6·6·7·8·8쪽.
  쪽이 거꾸로 가는 곳 3곳은 모두 존재 문항을 당긴 자리다(26쪽 동반질환 → 13쪽 ILD 앞, 20쪽 Bohan–Peter·25쪽 → 15쪽 EMG 앞, 28쪽 ILD 치료 → 23쪽 면역억제제 앞).
  이전 계산은 첫 문항이 26쪽, 「세 가지 범주」 63번째였다.
- 시험일을 12-10으로 두면(하루 새 목표 3개) 첫날 「정의와 아형」이 들어온다. 이전에는 들어오지 않았다.

## 배포 대상 버전·순서·데이터 변경

- 서버 계산만(`server/app/root_learning/planning.py`). DB·문항·학습 기록 변경 없음.
- master 병합 = API 자동 배포. 병합은 따로 승인받는다.

## 배포 후 확인·롤백·필요한 사람 승인

- 확인: 배포 후 피부근염 오늘 학습의 첫 문항이 6쪽 문항인지.
- 롤백: revert 또는 이전 Cloud Run revision.
- 승인: Ready·병합.
