# Main-Quiz 공개 판 중복 재판정·선지 병렬 — 배포 준비

## 코드 리뷰·검증 결과
2026-11-12 로컬(worktree `../Study_EZ_dedupe-published`, origin/master ceff852d 기준):
- 회귀: `pytest tests/contracts tests/quizbank tests/runner` — 리뷰 수정 뒤(a4ca5298) 2224 통과·1 건너뜀·1 실패(같은 기존 결함). 수정 전: 2220 통과·1 건너뜀·1 실패. 실패는 `test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`(바로가기 설치기, 기존 결함, 이 변경이 건드리지 않음). 기록 `runs/_development/2026-11-12-dedupe-published/*-regression.log`
- 새 검사: `tests/quizbank/test_dedupe_published.py` 4, `tests/runner/test_dedupe_published_runner.py` 4, 선지 묶음·강의 병렬 3(기존 18에 더해) 통과.
- 서버: `-m tests root_restart` 통과(duplicatesOnly 422 규칙·packet 표시·공개 판 유지). `-m tests root` 38 중 36 통과 —
  실패 2(`test_root_map_tree`, `test_root_map_tree_v3`)는 로컬 서버 venv에 PyMuPDF가 없어 import에서 실패(이 변경과 무관, CI에서 돈다).
- 실제 5편 무모델 재생(A4): 이 PC의 게시 결과에 이전 판정을 그대로 돌려주는 가짜 판정으로 duplicates-only를 돌렸다.
  모두 과제·커버 행이 이전과 같고 `generation_v4.validate_result`를 통과했다. 재판정 호출 수: 진단 1·치료원칙 1·병인론 2·병리2 2·피코르나 1.
  치료원칙 결과는 러너의 `completed_result`(영수증 `validate_all` 포함)도 통과했다.
- 선지 병렬: 병합 전 worktree 코드로 2026-11-12 13:3x부터 수정 대상 밖 18강의를 3강의씩 작성·업로드 시작(서버 선지 경로는 #118로 이미 배포).
- 독립 리뷰(읽기 전용 하위 에이전트)가 찾은 결함 4건을 고쳤다.
  1. map-tree 생성 packet은 source-assessment/2라 러너가 `runner.root_native_json`을 부르는데 그 main에 `--duplicates-of`가 없어 실제 실행이 시작에서 멈췄을 것 → 플래그를 받아 생성기에 넘긴다(검사 추가, 가짜 packet에 형식을 넣음).
  2. 묶음 판정이 다른 목표의 근거 문항을 묶음에 넣을 수 있었다 → 재판정의 근거는 받지 않아 묶음은 그 목표가 이미 근거로 가진 문항만 남는다.
  3. 새 단계도 manifest의 이전 모델로 검증된다 → 지금 모델이 이전 실행 모델과 다르면 호출 전에 거절(5편 모두 gpt-6.1-sol, 현재 기본값과 같음).
  4. 영수증 연결 중 중단되면 다시 돌 수 없었다 → `.seeding` 표시가 있으면 다시 연결하고, 남은 항목은 지운 뒤 연결(이전 실행 파일에 덮어쓰지 않음).
  - 선지 `--no-upload`에서 한 강의의 예외가 나머지를 멈추던 것도 고쳤다.
  - 남긴 낮은 위험: manifest의 `stageResumes` 등은 이전 실행 것이 그대로다(새 단계의 재시도는 ledger에만 남는다). /4 검증은 이를 보지 않는다.
- 확인하지 못한 것: 실제 모델이 묶는 중복의 양과 타당성. 운영 실행의 manifest `duplicatesOnly.changedGroups`로 본다.

## 배포 대상 버전·순서·데이터 변경
- PR 병합 → master 검사 → API → 웹 자동 배포. DB 스키마·결과 형식·서버 검증 변경 없음(RequestIn 선택 필드 하나).
- 러너: 병합 커밋으로 `.runtime/main-quiz-<sha12>` 설치 → 도는 작업이 없을 때 에이전트 교체.
- 운영: 5편(261102_02·03·05, 261104_03, 261111_02)에 「중복만 다시 판정」 요청 → 러너가 게시하면 학생은 새 판을 본다(학습 기록 미승계, 사용자 확인).
  선지는 새 판 게시 뒤 그 5편까지 포함해 공개된 감염과 면역 전부에 붙인다.

## 배포 후 확인·롤백·필요한 사람 승인
- `/api/health` revision, 러너 `agent.lock` pid와 PYTHONPATH.
- 5편마다: 새 실행 폴더의 `generation/result.json` manifest `duplicatesOnly`(판정 목표·바뀐 묶음·과제 전후), 서버 control이 새 판, 근거 asset이 새 판 이름.
- 선지: 강의마다 `choices/<revision>.json` 요약(작성·건너뜀·실패 묶음), 업로드 성공 로그.
- 롤백: `git revert` PR. 판은 옛 판이 DB에 남아 있어 control을 되돌릴 수 있다(별도 조치). 선지 asset을 지우면 그 강의의 선지가 꺼진다.
- 승인: 사용자 2026-11-12 요청과 질문 답(intent.md). 위장관·피부연조직 중복 재판정·다른 과목은 범위 밖.

## 운영 결과 (2026-11-12)
- 병합 acced192, API health revision acced1920d90 확인. 러너 `.runtime/main-quiz-acced1920d90` 설치, 에이전트 pid 38140(14:06, PYTHONPATH 새 설치본).
- 요청 영수증 `runs/_development/2026-11-12-dedupe-published/receipt.jsonl`(jobs 605~609, 모두 그 강의의 공개 판 = 이 PC의 마지막 게시 실행이었음).

| 강의 | 새 판 | 과제 | 재판정 목표 | 바뀐 묶음 | 근거 |
|---|---|---|---|---|---|
| 병인론 261102_02 | auto-00f6cecc | 152 → 145 | 62 | 7 | 이전 판 근거 재사용 |
| 진단 261102_03 | auto-5cbd6184 | 121 → 112 | 44 | 9 | 〃 |
| 치료원칙 261102_05 | auto-3e7385a6 | 116 → 114 | 52 | 2 | 〃 |
| 병리2 261104_03 | auto-f68cb4ce | 210 → 203 | 93 | 7 | 〃 |
| 피코르나 261111_02 | — | 155 (그대로) | — | — | 거절 |

- 강의마다 재판정 호출 1~2회, 판정 2~3분. 합친 묶음 대부분은 같은 답을 다른 발문으로 다시 묻는 것(예: 병인론 D010 Latent period 두 문항,
  병리2 D044 Langhans giant cell 두 문항). 갈래가 다른 내용을 묶었을 수 있는 것: 진단 D015(Q019 PCR 신속 확인 / Q020 항생제 독소 유리),
  D018(Q023 PCR 유용성 / Q084 sorbitol 무색 집락 감별), 병리2 DM019(Q086 aspergillosis 형태 표 / Q089 침습형 혈관 침범). 문항은 은행에 남는다.
- 피코르나: `이전 실행과 강의 입력이 다릅니다`로 모델 호출 전에 멈췄다. 2026-11-12 10:35에 올해 필기가 v2(`…오성연v2.pdf`, sha c30dfd19…)로 바뀌었고
  공개 판(cf4d5917)은 v1으로 만들어졌다. 공개 판은 그대로 학생에게 보인다. 처리(새 필기로 새로 출제 또는 유지)는 사용자 결정 대기. 서버 job 609는 실패로 남는다.
- 선지: 공개된 감염과 면역 23강의 전부 업로드. 수정 대상 밖 18강의(3강의씩, 13:24~13:50, 27분) 2,119문항 중 1,080 작성, 의학 검토가 뺀 오답 219,
  실패 묶음 0. 새 판 4강의 + 피코르나 현재 판: 569문항 중 287 작성. 합계 1,367문항. 화면에서 직접 열어 보지는 않았다(서버 업로드 완료 응답까지 확인).
- 피코르나를 새로 출제하면 그 새 판에 선지를 다시 붙여야 한다.
