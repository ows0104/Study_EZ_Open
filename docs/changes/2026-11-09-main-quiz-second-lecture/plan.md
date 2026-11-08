# Main-Quiz 생성 두 번째 강의 시범 — 사슬알균 — 구현 계획

## 변경 범위·대상 파일·순서
1. `run.py`·`run-all.sh`: `2026-11-08-importance-basis`의 사본이다. 바꾼 것은 강의 상수, `OUT=runs/_e2e/26110901`, `REVISION=map-tree-26110901`, Map 새 호출, 쪽 범위 문구뿐이다.
2. `bash run-all.sh points`: prepare → map → point → audit → (repair → final-audit) → verify-points → packet.
3. `bash run-all.sh generate` → `run results`.
4. 실패가 나면 원인을 기록한다. 엔진 수정이 필요하면 이 브랜치에서 재현 검사와 함께 고친다.

## 검사 명령과 성공 조건
- 코드를 고친 경우: 루트 `pytest tests`, `scripts/map_numbers --check`, 서버 root_·route_contract(격리 sqlite, `.env` 없음).
- 실행 성공 조건: `validate_result` 통과와 `generation-summary.json`.

## 위험·복원·승인할 범위
- 위험: 시간 초과, 공급자 콘텐츠 거절(간헐), 노트북 수면.
- 복원: 실패 폴더를 보존하고 다음 시도는 새 하위 폴더에서 한다.
- 승인: 외부 전송은 위 범위로 승인받았다. 운영 반입·학생 공개는 별도로 승인받는다.
