# Main-Quiz 지도 관계 누락 검사 — 배포 준비

## 코드 리뷰·검증 결과
상태: 구현·검사 완료, **D(남으면 멈춤) 기준 재결정 대기**. 병합하지 않는다.

검사(2026-11-14, 로컬):
- `python -m pytest tests`: 2972 통과, 4 건너뜀, 1 실패 — `tests/runner/test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`
  (PowerShell `PathNotFound`, 바로가기 설치 환경 문제, 변경 파일 무관). CI에서 다시 확인한다.
- 새 검사: `tests/contracts/test_relation_findings.py` 4개, `tests/quizbank/test_map_relation_guard.py` 6개,
  `tests/quizbank/test_place_by_review.py`의 /1 ledger 회귀 1개(기존 동작 보존).
- 서버 `python -m tests root`(메인 체크아웃 .venv, `PYTHONPATH=..`): 43 중 41 통과. 실패 2개(`test_root_map_tree`, `_v3`)는
  서버 venv에 `pymupdf`/`fitz`가 없어 import에서 멈춘 환경 문제다.
- 웹 `tsc --noEmit`: 변경 파일 오류 없음. `RootPdfSlides.tsx`의 `pdfjs-dist` 오류는 메인 체크아웃의 오래된 node_modules 탓(연결해 씀).

저장 산출물 재조립(모델 호출 없음, scratchpad `replay_b.py`): 운영판 28편 모두 /1 규칙으로 게시 결과와 같고,
/2 규칙(B)으로 계약 검증 통과. 미배치 232 → 177, B 배치 55(장내세균 43·나머지 12). C 대상 175(임시 조립 = 최종 조립 일치 확인).

실측(모델 호출 있음, `C:\Users\ows01\AppData\Local\Temp\s3r\{ped,pic}`, 운영 쓰기 없음, scratchpad `replay_live.py`):
기록된 단계는 입력 지문이 같으면 기록 출력을 썼고 새 단계만 Codex로 불렀다. medical-0 전에서 멈추게 했다.
| 편 | 기존 미배치 | B+C로 붙음 | 남음(D 멈춤) | 늦은 보충 호출 |
|---|---|---|---|---|
| 소아감염 fea11389 | 17 | 7 (B·C 배치 6, 합침 1) | 10 | 5 (약 6분) |
| 피코르나 9cb48bf1 | 13 | 0 | 13 | 5 (약 5분) |
- 늦은 보충 판정: 소아감염 13개 중 point 4·duplicate_of 9, 피코르나 13개 중 point 1·duplicate_of 12.
- 소아감염 남은 10개: 범위 점검은 답으로 본 문항이 있으나 그 관계가 지도 점검에서 `conflict`(FR036·FR050·FR058)
  또는 `unknown`(FR081·FR082)이다. 지지되지 않은 관계로는 과제가 될 수 없다(기존 learning_links 규칙).
- 피코르나 남은 13개: 보충 판정은 기존 포인트의 중복(duplicate_of)이나, 그 목표에 다시 판정하면 component를 답으로 묻지
  않는다(요소가 발문에 `provided`이거나 `missing`).
- 결론: D를 그대로 두면 정상 편 대부분이 게시 전에 멈춘다. 기준 재결정 필요.

## 배포 대상 버전·순서·데이터 변경
미정(D 결정 후). 데이터 변경 없음. 병합 시 API·웹 자동 배포, 이후 러너 .runtime 재설치.

## 배포 후 확인·롤백·필요한 사람 승인
병합·러너 재설치·261105_03 재출제는 각각 사용자 승인. 롤백은 PR revert(기존 /1 ledger·게시판은 /1 규칙 그대로 재검증).
