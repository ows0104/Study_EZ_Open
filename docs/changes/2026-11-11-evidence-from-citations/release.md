# 근거 지면을 출제 인용으로 바로 연결 — 배포 준비

사용자 2026-11-11 「구현 시작」(spec 결정 1·2 뒤). 브랜치 `claude/evidence-from-citations`, 기준 master `c4e455bb`.

## 코드 리뷰·검증 결과

### 바뀐 것
- **검토 근거 쪽 (R1)**
  - `studyez_contracts/roots/generation_v4.py`: `ITEM_REVIEW_EVIDENCE_OUTPUT`, `review_schema(ctx)`, `check_evidence`, `evidence_source`.
    - 검토 입력에 `evidence_source`(필기 PDF의 source_id·쪽 수)가 있을 때만 `evidence`가 필수다.
  - `runner/root_native_json.schema_for`가 같은 입력으로 출력 스키마를 고른다.
  - `content/prompts/learning-links/v4/item-review.md`에 `evidence` 줄을 더했다. 슬라이드·요약 쪽을 가리지 않는다(결정 1).
  - `quizbank/connection_generate_v4.py`: 새 ledger에만 `reviewEvidence: {policy: 'review-evidence/1', sourceId}`를 적는다(`Stages(fresh=…)`). 이 키가 없는 옛 ledger와 텍스트 필기는 지금처럼 돈다.
- **인용 맞추기 (R2)**
  - 시점: 모든 고치기(임상 정리 뒤 보완 포함)가 끝난 뒤, 조립·의학 검토 앞에서 한 번
  - 방법: `align_citations`가 S1 인용을 마지막 검토 근거 쪽으로 바꾸고 `citationAlignments`(바꾸기 전·후 `source_refs`)를 남긴다. 모델 호출이 없고 고치기 상한도 쓰지 않는다.
  - 계약(`_unalign4`/`check_alignments`, `generation_v3.check_result`의 add-only 검사가 사용)
    - 기록은 근거 쪽과 같아야 하고, S1 말고는 바뀐 것이 없어야 한다.
    - 기록이 없는 문항은 이미 근거 쪽을 인용해야 한다.
    - 검토 행은 판정 기록(`verdictLedger`)의 실제 판정이어야 한다.
    - 고치지 않은 접수 문항은 바꾸기 전 형태가 접수 때와 같아야 한다.
    - /3 결과와 옛 /4 결과에는 두 키가 없어야 한다.
- **게시 뒤 근거 (R3)**: `runner/root_evidence.publish` → `quizbank/root_evidence --reviews --review-source`
  - 검토가 증명한 문항은 `slide_focus.select(authored=…)`로 그대로 쓴다.
  - unresolved, 다른 원본, 보기 풀 후보만 다시 고른다.
- **재선택 묶음 (R4)**: `quizbank/slide_focus.py`
  - 대상이 40개를 넘으면 `batch-<n>/`로 나눠 최대 3개를 동시에 부른다.
  - 묶음 하나라도 실패하거나 다른 묶음의 대상을 고르면 전체 실패로 둔다.
  - 40개 이하는 지금처럼 한 번 부른다.
- **문서**: `quizbank/CLAUDE.md`(두 줄), `docs/map.md`(한 행), v4 `PROVENANCE.md`

### 독립 리뷰 (하위 에이전트, 코드만 주고 결론은 주지 않음)
- **결함 1, 심각, 수정함**: 생성기의 `notes` 변수가 임상 정리 보완의 `notes`와 이름이 겹쳤다.
  - 증상: 보완이 열린 새 실행이 재검토(`v4-review-context-1`)에서 멈춘다.
  - 수정: 변수 이름을 `evidence_notes`로 바꿨다.
  - 검사 `test_a_context_repair_re_review_keeps_the_notes_pages`를 더했다. 리뷰어가 재현한 경로다.
- **결함 2, 중간 이하, 수정함**: 결과 안의 `itemReviews`만으로 정렬을 확인하고 있었다.
  - 수정: 검토 행이 `verdictLedger`의 판정 값이어야 하도록 묶었다.
  - 검사 `test_the_consumer_refuses_review_evidence_that_is_not_a_recorded_judgment`
- **지적 3**: spec이 「임상 정리 앞」이라고 쓴 것을 구현(모든 고치기 뒤)에 맞춰 spec·plan을 고쳤다.
- **지적 4, 남김**: 묶음마다 쪽 이미지 폴더를 복사한다. 리케차 41쪽 기준 묶음당 수 MB이다. 이미 돌던 묶음의 사용량은 한 묶음이 실패하면 기록되지 않는다.
- **지적 5, 수정함**: 검사 도구가 다시 쓴 `web/public/bank-prompt.json`의 줄바꿈 변경을 되돌렸다. 커밋에 넣지 않는다.

### 검사
- **새 검사**: 모델 호출 0이고, 수정 전 master 코드(`c4e455bb` 사본)에서 실패하는 것을 확인했다.
  - `tests/quizbank/test_review_evidence.py` 12개: 수정 전 9개 실패. 통과한 1개는 텍스트 필기 호환 검사이며, 이후 추가한 2개는 리뷰 결함 검사다.
  - `tests/quizbank/test_root_evidence.py`에 3개, `tests/runner/test_root_evidence_publish.py`에 1개: 수정 전 4개 모두 실패
  - `tests/quizbank/test_slide_focus_batches.py` 4개: 수정 전 3개 실패. 통과한 1개는 40개 이하 호환 검사다.
  - `tests/runner/test_review_evidence_schema.py` 2개
- **전체 `python -m pytest tests`** (`development.py verify --check regression`, 리뷰 수정 전 1차): 2,743 통과, 4 건너뜀, 1 실패
  - 실패한 1개는 `test_desktop_control::test_shortcut_installer_supports_korean_filename_in_windows_powershell`로, master에서도 실패하는 기존 결함이다.
  - 기록 도구의 종료 코드 2는 prepare-prompts가 `bank-prompt.json`을 다시 쓴 탓이다(알려진 동작).
  - 리뷰 수정 뒤 2차 결과는 아래 「최종 검사」에 적는다.
- **서버 `-m tests root`** (worktree 계약, `PYTHONPATH=..`, 격리 sqlite): 29/31 통과
  - `test_root_map_tree`·`test_root_map_tree_v3`는 로컬 서버 venv에 PyMuPDF가 없어 import에서 실패한다. 이전 기록과 같은 환경 문제이고, CI는 의존성을 함께 설치한다.
- `scripts/map_numbers.py --check`: 정상
- **공개된 판 재검증**(읽기 전용, `validate_result`·`validate_all`): 이 브랜치와 master `c4e455bb`의 결과가 같다.

  | 판 | 결과 |
  |---|---|
  | `auto-1c484a7b…` (261102_02 /3) | 통과 |
  | `map-tree-26110803` (generation-3) | 통과 |
  | `auto-fa71412a…` (리케차 /4) | 거절 |

  - 리케차 거절 사유는 「assessment is not the gathered judgments」다.
  - 이 판은 만든 코드(`3b17af44`)로는 통과한다. master의 PR #90(place-by-evidence)이 /4 조립을 바꾼 뒤부터 거절되며, 이번 변경과는 무관하다.
  - 서버는 판을 받을 때만 검증하므로 공개된 판에는 영향이 없다. 다만 같은 결과를 다시 반입하는 일은 막힌다. 이 내용은 사용자에게 따로 알린다.

### 최종 검사
- 리뷰 수정 뒤 전체 `python -m pytest tests`(`verify --check regression`, 로그 `runs/_development/2026-11-11-evidence-from-citations/1794360792819937400-regression.log`): 2,745 통과, 4 건너뜀, 1 실패
  - 실패한 1개는 같은 기존 결함 `test_desktop_control` 한글 바로가기다.
- 리뷰 수정 뒤 관련 파일: `test_review_evidence.py` 12개 통과(보완 재검토·판정 기록 위변조 포함)

## 배포 대상 버전·순서·데이터 변경
- PR 하나를 master에 병합하면 API·웹이 자동 배포된다. 서버·웹 코드 변경은 없지만, 서버가 쓰는 계약(`studyez_contracts`)이 바뀐다.
- DB 스키마·데이터 변경은 없다. 새 키는 결과 manifest와 ledger 안에만 있다.
- **순서**: 병합(API 배포) → 러너 재설치
  - 새 러너가 만든 결과(인용 맞춤 포함)는 옛 서버 계약이 「changed without a fix」로 거절한다. 그래서 API가 먼저 나가야 한다.
  - 옛 러너가 만든 결과는 새 서버 계약도 받는다(새 키 없음).
- 러너 재설치는 병합 뒤 따로 한다. 대시보드에서 다른 세션의 실행 중 Main-Quiz 작업(병인론 /4 시범 등)이 없는지 확인한다.

## 배포 후 확인·롤백·필요한 사람 승인
- **확인**
  - `/api/health` revision이 병합 SHA인지 본다.
  - 다음 Main-Quiz 관리자 요청 때 근거 단계의 `slideFocus.authoredCount`·`reselectedCount`, 근거 단계 시간, `citationAlignments` 수를 이 파일에 적는다.
  - `citationAlignments`는 원본 쪽과 대조해 몇 건을 맞게 고쳤는지 적는다.
- **롤백**: git revert와 이전 Cloud Run revision·Pages로 되돌리고, 러너는 이전 설치본으로 다시 띄운다.
  - 새 정책으로 만든 판은 되돌린 서버에 다시 반입할 수 없다(옛 계약). 이미 게시된 판은 그대로 읽힌다.
- **사람 승인**
  - 실제 강의 자료 전송과 학생 공개는 관리자 화면 요청이 강의마다의 승인이다(기존 규칙). 이 변경이 따로 실행하지 않는다.
  - 공개된 판의 근거 재생성은 하지 않는다(spec 결정 3).
