# Main-Quiz 중요도를 출제 단계로 · 포인트는 누락 점검표로 — 배포 준비

## 코드 리뷰·검증 결과
- 진행: 사용자 「B, C 진행하고 같이 병합하자」(2026-11-10)에 따라 PR A·B·C를 브랜치 `claude/importance-at-authoring` 하나에 쌓았다. 병합은 #85 하나로 한다.
  - plan은 A 병합 뒤 B를 시작하도록 되어 있었지만, 이 지시로 순서를 바꿨다.
  - PR C가 겹친다고 적었던 #28은 이미 11-08에 병합된 상태였다(대시보드 행이 정리되지 않았을 뿐).
- 독립 리뷰(별도 에이전트, 2026-11-11): `/2`·`/3` 동작 변화는 없음을 확인했다.
  - `_prompt_hash` 기본값, `check_result` 메시지·정규식, `target_axes` 포인트 표, map_tree, root_front, root_native_json의 v3 경로, 서버 `_rate` 추출과 `/2` plan을 확인했다.
  - `/4` 결함 5건을 고쳤다.
    1. 러너가 완료된 `/4` 결과를 `repairRounds`로 검사해 모두 거절하던 것(`runner/connection_generation.py`)
    2. 중복 묶음이 연쇄될 때 이미 남긴 문항을 다른 묶음에서 합쳐 목표가 비던 것. 이제 남긴 문항은 다시 합치지 않고, 목표에 못 붙는 문항은 남길 문항으로 고르지 않는다.
    3. 판 사이 승계 지문이 은행 전체 맥락을 포함해 사실상 이어지지 않던 것. 이제 문항 자체 내용 지문(`question-content/1`, tier·importance 제외)을 쓴다.
    4. 고치지 않은 intake 문항의 basis를 결과 검증에서 intake 원문과 대조하지 않던 것
    5. recall-unit 목표에서 배치·readiness가 부모 ID를 못 찾던 것
  - 각 결함에 회귀 검사를 더했다.
- 검사:
  - `pytest tests/contracts tests/quizbank`: 1272 passed(`development.py verify` 기록).
  - `pytest tests/runner`: 783 passed, 1 failed. 실패한 `test_desktop_control`은 master에서도 실패하는 기존 결함이다.
  - 서버 `-m tests root`: 29/31. `test_root_map_tree`, `test_root_map_tree_v3`는 로컬 venv에 PyMuPDF가 없어 import에서 실패한다(환경 문제로 이 변경과 무관하고, CI에는 있다).
  - 서버 `-m tests main_quiz`: 6/6.
  - 웹 `npm run typecheck`·`npm run build` 통과.
- 실제 모델 시범은 하지 않았다(승인 범위 밖).

## 배포 대상 버전·순서·데이터 변경
- master 병합이 곧 자동 배포(검사 → Cloud Run API → Pages)다.
- DB 스키마 변경은 없다. `/4` 학습 이벤트에 `question_sha256` 칸이 JSON payload로 더해질 뿐이다.
- 기존 판·학습 기록·Quiz Bank는 바뀌지 않는다. `/2`·`/3` 문서는 기존 코드 경로를 그대로 쓴다.
- 관리자 생성 요청의 기본값은 그대로(map-tree/1)다. 「새 구조 2 (시범)」(map-tree/3)을 고를 때만 `/4`가 돈다.
- 러너가 `/4`를 실행하려면 새 코드로 러너를 다시 설치해야 한다(별도 승인, 메모리의 「러너 새 코드 반영 절차」).

## 배포 후 확인·롤백·필요한 사람 승인
- 확인:
  - Actions 성공
  - `/api/health` revision이 병합 SHA인지
  - Pages 청크에 「새 구조 2」 문구가 있는지
  - 기존 Main-Quiz 강의(261104_02, 261105_01) 학습 화면이 그대로인지(읽기 전용)
- 롤백: 병합 커밋을 되돌린다. `/4` 판이 아직 없으므로 데이터 되돌림은 없다.
- 별도 승인이 필요한 일:
  - 러너 재설치
  - 실제 모델 시범(필기·족보 OpenAI 전송)
  - 261102_02를 `/4`로 다시 생성하는 것
  - 운영 반입·학생 공개
