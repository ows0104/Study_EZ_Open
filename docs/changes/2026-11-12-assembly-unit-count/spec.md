# Main-Quiz 조립 검사: cloze 답 단위 수·접수 탈락 번호 재사용 — 설계

## 요구사항과 수용 기준
- R1 `_compile`의 `answer_unit_indices` 상한은 커버 판정이 본 앞면(`v3._front` = `normalize_cloze`)의 답 단위 수다.
  표 한 줄에 빈칸이 둘인 cloze는 저장된 `answer_units`(줄당 하나)보다 보이는 단위가 많다. `check_coverage`는 이미 보이는 단위로 센다.
- R2 `validate_result`의 접수 중요도 근거 대조는 `rejectedAtIntake`에 있는 번호를 뺀다.
  탈락한 문항은 문제은행에 없고, 추가 출제가 같은 번호로 새 문항을 쓸 수 있다(다음 번호는 남은 문제은행의 최댓값 뒤부터).

## 책임·입출력 계약·오류 상태
- `studyez_contracts/roots/generation_v4.py`만 바뀐다. 결과 형식·단계 입력·지시문·DB 불변. 서버도 같은 계약으로 결과를 검증하므로 서버 배포가 러너보다 먼저다.
- 인덱스가 보이는 단위 수를 넘거나 중복이면 지금처럼 거절한다.

## 호환성과 데이터 보존
- 단계 입력 지문이 바뀌지 않아 기존 실행은 완료 단계를 그대로 쓰고 이어진다.
- `answer_unit_indices`를 읽는 곳은 계약 검사뿐이다(server·web에는 없음).
