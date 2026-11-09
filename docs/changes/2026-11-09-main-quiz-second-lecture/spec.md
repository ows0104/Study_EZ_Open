# Main-Quiz 생성 두 번째 강의 시범 — 사슬알균 — 설계

## 요구사항과 수용 기준
- 감염병리1 `run.py`와 같은 단계·지시문·검사를 쓴다. 엔진·프롬프트·계약은 이 작업으로 미리 바꾸지 않는다.
- 단계마다 상태를 `runs/_e2e/26110901/<단계>/state.json`에 남긴다. 실패하면 `failure.json`에 남긴다.
- 실패하면 그 자리에서 멈춘다. 고칠 때는 감염병리1 때처럼 실패를 재현하는 검사부터 쓴다.

## 책임·입출력 계약·오류 상태
- 입력: SynologyDrive 필기 원본과 교수우선 v2 족보. 둘 다 sha256을 고정한다. prepare가 `material/`에 사본을 얼린다.
- 출력: `runs/_e2e/26110901/`(git 밖)과 `generation/result.json`.
- 계약: exam-point-extract/3, root-generation/2, Bank 3.3, `validate_result`.

## 호환성과 데이터 보존
- 서버·운영 DB·R2·큐는 건드리지 않는다.
- 원본 자료는 읽기만 한다.
- 실패한 폴더는 보존하고 새 폴더에서 다시 돈다.
