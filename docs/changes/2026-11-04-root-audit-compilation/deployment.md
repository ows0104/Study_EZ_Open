# 원인 수정 완료

AI가 고정 지도/ID/hash/중복 역할/coverage까지 동시에 작성하던 구조와, 검수 기록 계약 오류를 BANK-only 수정에 전달하던 흐름을 수정했다. 새 source-assessment/1은 독립 의미 판단만 반환하고 입력별 스키마/순수 compiler가 기존 엄격한 AUDIT로 조립한다. 새 요청의 입력 지문에 형식 버전을 고정해 원문 증거를 전부 제거한 구형 수용 경로로 우회하지 못하게 했다. 구형 정상 결과의 호환은 유지한다. 단일 문항이 방향 전체를 시험해야 과제가 된다는 기준, 의학 검수 판정과 수정/검수 상한은 바꾸지 않았다.

최종 고정 사본 source87a74bb17e50d586f58fa657cff293caf691da7acd9da56fc19720c291b98ef2 / plan98163db11732825d20df2489929073f6c21194f78ea9420c82ddde1761def83a: 계약96·생성59·러너29 및 격리 서버6묶음 통과. 실제 gpt-6.1-sol의 작은 비의학 가상 예제2문항은 새 스키마 응답→엄격한 AUDIT→방향 전체 과제2개 생성에 성공했다. 운영 자료 사용/게시/추가 의학 검수는 없다. 최종 코드에서도 원문을 추가 모델 호출 없이 동일하게 조립하는 것을 확인했다. 실행 입력/schema/raw/usage/audit/document/summary와 검사·리뷰·승인·배포 영수증은 verified-scope에 보관했다. 이 고정 사본이 정본 근거이며 원래 작업 폴더의 다른 미커밋 변경을 검사/배포한 것으로 취급하지 않는다.

최종 API candidate ed9553c06e2505434641c7644626448e162a72779e33380012f28c9ad63ea5a0 → studyez-api-release-1793760893095067800. Ready/ContainerReady/latestCreated/latestReady와100% 트래픽 확인 후 health/auth/root 읽기 전용 사후 검사 통과. 최초 호환 소비자 revision1793760592795137800도 성공했으며 마지막 packet-version 바인딩은 별도 최종 후보/검사/배포로 남겼다. 웹57fe6571-2415-4250-9895-e5f2bb903171, DB 스키마/권한/기존 학습 데이터는 변경하지 않았다.

원래 콜린성(1) 예시 generation f0a8f3b68e3642598f85bbf462e1dc55/job524의88문항·13단계·수정3회·검수4회와 실패 기록은 보존했다. 이 예시는 게시하지 않았고 재호출/상한 초기화하지 않았다. 기존69문항/build/status/bank/validation/review6개 baseline 값은 그대로다. 원래 부분 채택 제안은 사용자의 원인 해결 지시로 대체했으며 구현하거나 승인을 다시 요청하지 않는다.

로컬 생성기와 고정 검증 사본의 runtime 의존 파일을 대조했다. 유일한 byte 차이는 이번에 수정하지 않은 quizbank/session.py의 CRLF/LF이며 정규화한 내용은 정확히 같다. 나머지 의존 파일 bytes는 모두 일치한다. 양쪽 runtime hash와 파일 hash를 local-runtime-comparison.json에 구분해 기록했고, 원래 파일과 기존 원장 identity를 덮어쓰거나 같은 hash라고 주장하지 않았다. API 산출물에는 해당 로컬 session 파일이 포함되지 않는다.
