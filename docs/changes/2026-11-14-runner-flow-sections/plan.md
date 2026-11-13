# 러너 창 흐름 순서 — 구현 계획

## 변경 범위·대상 파일·순서
1. `runner/status_window.py`: 카드 영역 앞에 `build_before_jobs(root)` 빈 훅, 카드 영역 뒤 기존 `build_controls`. 그 밖은 그대로.
2. `runner/desktop.py`: 한 표를 네 구역으로 나눔.
   - 순수 함수 `sections(rows, waiting)` → `{'choose','queue','running','finished'}` 행 목록(정렬 포함), `state_label(row)`(기존 라벨 규칙 이동).
   - ① 접힘 구역·② 대기열 표를 `build_before_jobs`에, ③ 실행 중 작은 표·④ 완료·실패 표·로그 칸을 `build_controls`에.
   - 구역별 버튼, 단일 선택, ④ 선택 시 로그 표시(`status.tail`).
3. `tests/runner/test_desktop_window.py`: 구역 분류·정렬·버튼 종류·단일 선택·로그 표시 검사 추가, 기존 검사는 새 선택 방법으로 갱신.
4. `runner/CLAUDE.md` 바탕화면 창 문단 한두 줄.

## 검사 명령과 성공 조건
- `C:/Users/ows01/anaconda3/python.exe -m pytest tests/runner -q` 통과(worktree에 .venv가 없어 생기는 바로가기 설치기 검사 1개는 기존 결함으로 구분).
- 실제 `runs/`로 `pythonw -m runner.desktop --no-auto-start`를 이 worktree에서 띄워 네 구역 스크린샷 확인. 자동 시작은 끈다.

## 위험·복원·승인할 범위
표시만 바뀐다. 병합만으로 실행 중 러너·창에는 반영되지 않는다. 반영은 `.runtime` 재설치 후 바로가기로 다시 열기(실행 중 강의가 끝난 뒤).
되돌리기는 revert 후 재설치. 승인 범위: 위 파일과 이 작업 폴더. 러너 실행·서버·DB 불변.
