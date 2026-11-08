# 감염병리1 Map 파이프라인 재구성(개념 트리·구조 문제) — 배포 준비

감염병리1 실행은 결과 없이 중단했다([stopped.md](stopped.md)). 이 브랜치의 PR은 엔진·계약·프롬프트 수정만 올린다.
생성된 Map·포인트·문항(`runs/_e2e/26110801/`)은 git 밖에 있고 등록·공개하지 않는다.

## 코드 리뷰·검증 결과

- Map 추출 `/3`: `parent_id` 개념 트리. `/2` 프롬프트·스키마·예시는 `*-v2.*`로 보존.
- 계약: `learning_links/concept_tree.py`(뿌리 1–8, 깊이 ≥2, 순환·미지 부모 없음), 정규화의 부모 보존 검사.
  `roots/generation_v2.py`: 렌더 복구·정답 검수 재검수·순차 런타임 재검증 기록 검증, PDF 판정의 frozen localPath,
  트리 전용 개념의 은행 투영(`container-concepts/1`)과 지문 재결합, 중요도 보완(`importance-review/1`) 계속 경로.
- 생성기: 큰 crop의 단계적 축소(2→0.75배), 독립 정답 검수의 문항별 판정 강제, 계층 결함의 map_fix 사유.
- 러너 도구(모두 명시 승인 뒤 수동 실행): `root_render_recovery`·`root_medical_retry`·`root_runtime_revalidate`·
  `root_importance_review`. 중요도 도구는 묶음마다 즉시 저장·재사용하고 최종 대조 시한은 5400초다.
- 검사: 루트 `pytest tests`(CI와 같은 제외 + 환경 문제인 `test_desktop_control` 바로가기 1건 제외), `map_numbers --check`.

## 배포 대상 버전·순서·데이터 변경

server/·web/ 파일 변경은 없지만, API가 업로드 결과를 `studyez_contracts.roots.generation_v2.validate_result`로
검증하므로 계약 변경은 서버에도 닿는다. 추가는 하위 호환이다: 새 복구 기록(렌더·재검수·순차 재검증·은행 투영·
중요도 보완)이 없는 기존 결과는 그대로 통과한다. 새 기록이 든 결과를 올리려면 API를 먼저 다시 배포해야 한다
(푸시는 프론트만 배포하고 API는 `deploy.ps1`로 따로 올린다). 지금 그런 결과는 없다.
기존 `/2` 진행 중 ledger는 런타임 신원이 바뀌므로 이어 쓸 때 `root_runtime_revalidate`(모델 호출 없음)를 먼저 거친다.
DB·운영 문항·학습 기록·수정 상한 변경 없음.

서버 검사(브랜치 계약을 `PYTHONPATH`로 지정, 파일별 격리 sqlite): `root_` 23·`route_contract`·`study_retention` 통과.

## 배포 후 확인·롤백·필요한 사람 승인

병합 뒤 Pages 자동 배포는 돌지만 web/ 변경이 없다. 러너가 master를 받으면 그 뒤의 새 생성부터 crop 축소·문항별 정답 판정·
계층 검사(부모가 있는 Map일 때만)가 적용된다. Map `/3` 지시문은 자동 경로가 읽지 않는 수동 추출용이다. 서버는 재배포 전까지 기존 계약이다. 롤백은 병합 되돌리기.
API 재배포·감염병리1 재실행·운영 등록·학생 공개는 각각 별도로 한다.
