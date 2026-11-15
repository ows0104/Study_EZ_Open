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

결론: 늦은 보충만으로는 살리지 못한다. 결함 관계를 고치는 단계가 필요하다 → 사용자 「관계 수선 더해」(spec R4).

R4 실측(같은 사본, `o2`·`o3`):
- `o2`: 결함 관계 14개 모두 고침·다시 점검 14개 supported. **13 → 5**(과제 145 → 153), 10분 22초. 그러나 고친 관계·개념 이름이
  영어 문장이 됨(「More than 80% of Rhinovirus … bind ICAM-1.」) → 한국어 유지 지시 + 한글이 빠지면 거절하는 검사 추가.
- `o3`: 같은 결과 **13 → 5**, 과제 145 → 153, 범위 점검 판정 8개, 11분 28초, 모델 단계 6개. 한국어 유지 확인:
  FR024_02 「대부분 80% 이상은 ICAM-1 이용」 → 「Rhinovirus의 80% 초과가 ICAM-1에 결합함」, FR024_03 「PVR/CD155」 →
  「Poliovirus의 수용체는 PVR/CD155」, FR053_01 「Coxsackie B·Echo」 → 「신생아 질환은 Coxsackie B·Echo와 연결됨」.
- 남은 5개: 늦은 보충이 만든 새 목표에서 범위 점검이 component를 답으로 보지 않음(Q003·Q044·Q103 `missing`, Q092 `provided`),
  Q067(사진 문항)은 답으로 봤으나 관계를 적지 않음. 사유와 함께 관리자 결과에 남는다.

검사: `pytest tests/contracts tests/quizbank tests/runner` 2312 통과·1 실패(test_desktop_control 바로가기, 기존 환경 문제), R4 뒤
재배치·중복 재판정·러너 테스트 23개 통과(1 skip: 합성 관계에 한글 없음, 단위 테스트가 대신함).

## 배포 대상 버전·순서·데이터 변경
master 병합(API·웹 자동 배포: 서버 요청 필드만) → 러너 .runtime 재설치 → 편마다 `restart+replacePublished+unplacedOnly` 요청.
DB 스키마 변경 없음. 편당 약 11분(모델 6단계), 러너 동시 2편.

## 배포 후 확인·롤백·필요한 사람 승인
병합·러너 재설치·공개판 교체는 각각 사용자 승인.

## 운영 적용 1차 (2026-11-15)
- 러너는 다른 세션이 04c657fe(#181 포함)로 이미 재설치해 둠. 요청 2건(관리자 요청 경로, 사용자 「재설치·교체 시작」).
- 261111_02 피코르나 job 622: 게시·공개판 교체 완료. 미배치 13 → 3, 과제 145 → 155, 결함 관계 14개 수선(다시 점검 supported 10).
- 261106_06 무산소세균 job 623: 실패 — 한국어 검사가 PR014 「B. fragilis 25%, Cutibacterium acnes 19%, …」(균 이름·수치 목록)를
  거절. 검사가 모델 세션 밖에서만 돌아 모델이 고칠 기회 없이 편 전체가 멈췄다.
- 수정(브랜치 claude/repair-korean-check): 한국어 검사는 「한글 없음 + 영어 기능어(of·and·than·bind…)」만 거절. 관계 수선 검사와
  늦은 보충의 duplicate_of 검사를 모델 세션 안(runner v3_check, v4 check_stage)에서도 돌린다. 테스트 368 통과.
