# Main-Quiz 지도에 못 붙은 문항 재배치 — 배포 준비

## 코드 리뷰·검증 결과
구현(설계와 다른 점): 재배치는 이전 실행을 이어 돌리지 않고, 공개 결과에서 바로 다시 조립한다(`quizbank/connection_replace.py`).
문항·검토·의학 검토가 그대로이고, 중복 재판정(duplicates-only/1)으로 게시된 4편의 묶음도 보존된다. 늦은 보충의 범위 밖 판정은
문항을 빼지 않고 미배치로 남긴다. 관리자 화면 버튼(R3)은 만들지 않았다: 공개판 교체 요청 화면이 없고 중복 재판정도 스크립트로 요청했다.

검사: 새 테스트(`tests/quizbank/test_connection_replace.py` 5개, 늦은 보충 2개, 러너 분기·인자), 서버 `python -m tests root` 44 중 42
(pymupdf 없는 환경 2개), `test_root_restart`·`test_root_generation_columns` 통과.

실측(2026-11-15, 피코르나 261111_02 공개판 사본, Codex `gpt-6.1-sol`, 운영 쓰기 없음, `C:\Users\ows01\AppData\Local\Temp\s3r\pu`):
- 모델 단계 4개(supplement-late·supplement-normalize-late·coverage-supplement-late·map-check-late), 7분 35초.
- 늦은 보충: 13문항 모두 새 포인트(중복 판정 없음, 의도대로). 새 목표 11개, 범위 점검 `covered` 9개.
- **붙은 문항 1개(13 → 12).** 원인: 새 목표가 기존 지도 관계를 다시 쓰고(supplement-normalize는 목표·포인트만 더하고 관계를
  만들지 못한다), 그 관계가 지도 점검에서 `unknown`·`conflict`다. 예: FR024_02 「대부분 80% 이상은 ICAM-1 이용」은 rhinovirus를
  빼먹어 unknown, FR024_03은 poliovirus를 빼먹어 unknown, FR053_*는 질환 행을 빼먹어 unknown/conflict. 지지되지 않은 관계에는
  과제가 설 수 없다(기존 규칙). FR004_01은 늦은 점검에서 supported지만 먼저 내려진 conflict가 남는다(첫 판정 우선).

운영 27편 미배치 125개를 같은 기준으로 나누면(저장 결과, 모델 호출 없음):
| 문항이 범위 점검에서 묶인 관계 | 문항 |
|---|---|
| unknown·conflict 관계뿐 | 42 |
| 관계를 적지 않음 | 54 |
| 지지된 관계가 있음(답으로 묻지 않음 등) | 29 |
27편 관계 4198개 중 unknown 56·conflict 29(2%)인데, 못 붙은 문항이 거기에 몰린다.

결론: 늦은 보충만으로는 살리지 못한다. 결함 관계를 고치는 단계가 필요하다(사용자 결정 대기).

## 배포 대상 버전·순서·데이터 변경
미정(관계 수선 결정 뒤).

## 배포 후 확인·롤백·필요한 사람 승인
병합·러너 재설치·공개판 교체는 각각 사용자 승인.
