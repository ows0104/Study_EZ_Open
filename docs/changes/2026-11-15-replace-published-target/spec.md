# 공개판 재사용 경로(중복만·못 붙은 문항만)가 공개 판의 작업을 이전 판으로 — 설계

## 요구사항과 수용 기준
- R1 `restart_target(..., from_published=True)`(요청이 duplicatesOnly 또는 unplacedOnly): 지금까지의 거절(진행 중 작업, 다른 관리자)을 가장
  최근 요청에 그대로 적용한 뒤, `RootControl.revision`이 `auto-<id>`인 그 작업(같은 강의, packet.revision 일치, result_digest 있음)을 돌려준다.
  없으면 409 「지금 공개된 판을 만든 작업을 찾지 못했습니다」. 그 작업의 소유자도 요청 관리자여야 한다.
- R2 다시 출제(`restart`) 요청에서 `equivalent_generation`이 찾은 같은 입력 요청의 작업이 failed·canceled면 재사용하지 않고 새 요청을 만든다.
  입력 지문(`input_digest`, 이유 포함)까지 같으면 예전처럼 그 요청을 돌려준다(고유 조건 `subject, run_id, input_digest`).
- 수용: `server/tests/test_root_restart.py` — 공개 판을 만든 요청이 없으면 409, 중복만·못 붙은 문항만은 공개 판 작업을 `restartOf`로,
  못 붙은 문항만 시도가 실패한 뒤 새 이유의 재요청도 공개 판 작업을, 같은 이유면 실패한 요청 그대로, 일반 새로 출제는 가장 최근 요청.

## 책임·입출력 계약·오류 상태
서버 `server/app/routes/root_generation.py`만. packet 칸·러너·계약 불변. 오류는 409(공개 판 작업 없음·다른 관리자).

## 호환성과 데이터 보존
DB 스키마·기존 요청·이벤트 변경 없음. 실패한 요청은 그대로 남는다. 일반 「새로 출제」의 사슬(가장 최근 요청을 옆에 둠) 불변.
