# Main-Quiz 단답·나열 선지 보기 — 배포 준비

## 코드 리뷰·검증 결과
2026-11-12 로컬 검사(worktree `.worktrees/recall-choices`):
- 최종 전체 실행(5회차 지시문 직전 코드): `pytest tests/contracts tests/quizbank tests/runner` 2201 통과, 1 실패(바로가기 설치기 기존 결함).
  서버 `recall_choices` 1·`main_quiz` 7·`route_contract` 1 통과, `root` 34/36(PyMuPDF 없음). 웹 `npm run build` 통과. 5회차는 지시문 글만 바꿨다.
- `python -m pytest tests/contracts tests/quizbank`: 1379 통과.
- 파이프라인에서 떼어 낸 뒤 `tests/runner`의 선지·게시 경로 검사 43 통과. 그 전 전체 실행: 831 통과, 1 실패 — `test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`.
  바로가기 설치기 검사이며 이 변경이 건드리지 않는 기존 결함이다(대시보드 완료 기록의 「바로가기 설치기 1 기존 결함」).
- 서버 `-m tests recall_choices` 1 통과, `main_quiz` 7 통과, `route_contract` 통과, `root` 36 중 34 통과.
  실패 2(`test_root_map_tree`, `test_root_map_tree_v3`)는 로컬 서버 venv에 PyMuPDF가 없어서다(`No module named 'fitz'`). 이 변경과 무관하다.
- 웹 `npm run typecheck` 통과.
- 화면: `web/tests/root-recall-choices.test.cjs` 2 통과(검사용 API `server/tests/serve_main_quiz_recall_fixture.py`), 기존 `root-learning.test.cjs` 8 통과.
  화면 검사 중 찾아 고친 결함: 다음 문항이 그려지는 첫 순간에 앞 문항의 「폈음」 값으로 선지가 비쳤다(`RootSolve`의 폈음 상태를 문항 키에 묶음).
- 실제 모델 시범(리케치아 261110_03, 판 auto-fa71412a…, 올리지 않음, 2026-11-12). 대상 90문항:

  | 회차 | 지시문 | 작성 | 건너뜀 | 의학 검토가 뺀 오답 |
  |---|---|---|---|---|
  | 1 | 강의 안 오답만, 검토 없음 | 16 | 74(모델이 건너뜀) | — |
  | 2 | 강의 밖 허용 + 의학 검토 | 46 | 44(검토 뒤 부족 34, 모델 10) | 88 |
  | 3 | 2와 같고 검토 지시문 수정 | 74 | 16(검토 뒤 부족 6, 모델 10) | 7 |
  | 4 | 뻔한 오답 금지·헷갈리는 이유 필수 | 38 | 52(모델 48, 검토 뒤 부족 4) | 5 |
  | 5 | 4에서 「다른 장기계」 금지를 빼고 상식 기준만 | 40 | 50(모델 43, 검토 뒤 부족 7) | 10 |

  - 2회차의 88개 중 절반 이상은 「오답이 틀린 사실을 담았다」는 이유였다. 검토 지시문의 기준이 잘못된 것이라 뺐다(오답은 틀린 것이 정상).
  - 3회차가 뺀 7개는 모두 타당했다(예: 리케치아 네 속의 오답 Bartonella, DIC의 피브리노겐 증가, 표적 세포의 erythrocytes).
  - 작성된 74문항 중 22문항을 무작위로 읽었다. 정답으로도 성립하는 오답은 보지 못했다. 일부는 쉽다(기피제 문항의 자외선 차단제).
  - 3회차 74문항 중 15~20개에 상식·다른 장기계로 지워지는 오답이 섞여 있었다(사용자 지적 「털진드기 성충이 날개로 날아 이동한다」).
    4회차는 오답마다 헷갈리는 이유를 쓰게 하고 그런 오답을 금지·검토 대상으로 넣었다. 그 오답이 있던 12문항 중 11문항은 건너뛰고
    1문항(크기·형태)은 다른 세균 형태로 바뀌었다. 대신 선지가 붙는 문항이 74 → 38로 줄었다.
  - 5회차: 장기계를 허용해도 증상·합병증·감별진단 나열 문항은 「목록 밖이라도 실제로 나타날 수 있어 확실한 오답이 아니다」로 건너뛴다.
  - 한 강의의 결과다. 다른 강의·과목에서 같은 품질인지는 확인하지 않았다.
  - 호출: 작성 3회 + 검토 3회. 결과 `runs/_root-generation/fa71412a…/choices/`.

## 배포 대상 버전·순서·데이터 변경
- DB 스키마·기존 데이터 변경 없음. 새 asset 종류 `root_choices`는 코드 목록(`ASSET_KINDS`)에만 더한다.
- 순서: master 병합 → API → 웹 자동 배포. 러너 재설치는 필요 없다 — 게시 경로(`runner/connection_generation.py`)는 master와 같다.
- 누군가 `python -m runner.root_choices`를 돌려 올리기 전에는 아무 판에도 선지가 없으므로 화면·API는 지금과 같다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: API health의 revision, 선지 asset이 없는 강의의 풀이 화면이 그대로인지.
- 롤백: 병합 커밋 revert. 올린 asset을 지우면 그 강의의 선지가 꺼진다.
- 따로 승인: 리케치아 한 강의 시범(약 3회 호출), 이번 블록 공개 판 보강, 학생에게 처음 보이는 시점.
