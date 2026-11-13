# Main-Quiz 선지를 게시 직후 기본 실행 — 구현 계획

## 변경 범위·대상 파일·순서
| 순서 | 파일 | 내용 |
|---|---|---|
| 1 | `runner/connection_generation.py` | 게시·근거 보강 뒤 `root_choices.publish` 호출 |
| 2 | `runner/root_choices.py` | 업로드 표시 `choices/uploaded.json`, `uploaded()`, `--missing`, 끝 줄 「이미 있음」 |
| 3 | `tests/runner/test_root_choices_publish.py` | 「게시 경로는 부르지 않는다」 검사를 「게시 직후 부르고 실패해도 게시 성공」으로 교체, 표시·`--missing` 검사 |
| 4 | `tests/runner/test_connection_generation.py`, `test_dedupe_published_runner.py`, `test_root_front.py`, `test_root_front_v3.py`, `generation_fixture_worker.py` | 검사에서 선지 생성기(모델)를 부르지 않게 막기, 중복 재판정의 새 판에도 선지 |
| 5 | `docs/map.md`, `docs/artifact-contract.md`, `quizbank/CLAUDE.md`, `runner/CLAUDE.md` | 수동 → 게시 직후 기본 |

## 검사 명령과 성공 조건
- `python -m pytest tests/runner -q --ignore=tests/runner/test_desktop_window.py --ignore=tests/runner/test_status_window.py` (CI와 같은 범위)
- `python -m pytest tests/quizbank/test_root_choices.py tests/contracts/test_root_choices_contract.py`

## 위험·복원·승인할 범위
- 위험: 새 판마다 모델 호출이 강의당 약 6회 늘고 러너 일감이 그만큼 길어진다. 선지 오답 품질은 2026-11-12 시범·일괄 실행과 같은 지시문이다.
- 복원: 병합 커밋 revert 후 러너 재설치. 올린 asset은 남지만 판·문항과 무관하고, 지우면 그 강의의 선지가 꺼진다.
- 승인: 사용자 2026-11-14 「…안 돌아갔으면 해줄래? 그리고 기본으로 설정해줘」가 구현·병합과 게시 직후 선지 작성(판 문서 글을 모델에 보냄)의 기본화 승인이다.
  운영 반영에는 사용자 PC의 러너 재설치가 필요하다(이 세션에서 불가). 빠진 강의 보강 실행도 같은 발언의 범위이며 사용자 PC에서 돈다.
