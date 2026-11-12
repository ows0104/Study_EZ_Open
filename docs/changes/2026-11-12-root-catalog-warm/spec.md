# Main-Quiz 요약 빠르게(시작 때 가벼운 사본) — 설계

## 요구사항과 수용 기준
- `light.warm(db) -> (만든 수, 초)`: `RootControl.enabled and revision`인 강의를 하나씩 `current_rows`로 만든다(상한 LIMIT).
  한 강의 실패는 로그만 남기고 계속.
- `light._load`: 캐시에 없을 때 `_load_lock` 안에서 다시 확인 → 원본 읽기 → `lighten` → 캐시 → 세션에서 원본 행을 뗀다.
- `app.main.lifespan`: `ENVIRONMENT=production`이고 `STUDYEZ_WARM_MAIN_QUIZ != "0"`이면 `warm_main_quiz()`를 포트가 열리기 전에 부른다.
  Main-Quiz가 꺼져 있으면 건너뛴다. 예외는 로그만 — 서버는 뜬다.
- `LIMIT = 64`.

## 책임·입출력 계약·오류 상태
- 학습 상태 계산은 그대로(같은 `lighten` 결과). 사본 키(과목, 강의, 판, digest)도 그대로라 새 판은 새로 만든다.
- 시작 로그(WARNING): 「Main-Quiz 가벼운 사본 N편을 미리 만들었습니다 (x.x s)」 — 배포 뒤 관측용.
- 끄기: Cloud Run 변수 `STUDYEZ_WARM_MAIN_QUIZ=0`.

## 호환성과 데이터 보존
DB를 읽기만 한다. 학습 기록·문항·검수 이력 변경 없음.
