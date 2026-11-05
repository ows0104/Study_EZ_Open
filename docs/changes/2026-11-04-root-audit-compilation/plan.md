# 구현 계획

1. studyez_contracts/roots/source_assessment.py에 입력별 schema와 순수 compile 함수를 추가한다. 실제 문제의 방향 밖 관계/중복 역할/부분 충족 모순과 미시험/판단 불가/제외/방향 전체 과제 기준을 합성 자료로 재현한다.
2. quizbank/connection_generate.py와 source.md를 새 프로토콜로 전환한다. raw/usage 보존→compile/엄격 검증→완료 기록 순서로 바꾸고, 기술 실패는 content repair에 넘기지 않는다. raw 지문과 재개 보존, 최종 manifest 연결을 검사한다.
3. roots/automation.py 소비자가 마지막 raw의 지문·조립 결과를 재검증한다. 기존 정상 AUDIT와 이전 게시 결과는 호환 유지한다. 공유 합성 fixture의 모델 출력을 새 프로토콜로 바꾸고 HTTP 소비자 검사에도 새 결과를 포함한다.
4. 고정 tmp/root-web 사본에 이 관련 파일만 옮기고 development.py verify로 contracts 전체, 관련 생성기/프롬프트/런타임, runner HTTP/subprocess, 격리 root_generation/root_web_generation/root_one_click/root_preservation/route_contract를 실행한다. 실제 Codex의 작은 비의학 예시로 동적 출력 스키마와 compile 경로도 확인한다. 이는 기존 시범의 추가 내용 검수가 아니다.
5. 검사·리뷰 후 필요한 API 계약 고정 후보만 기존 승인 범위로 배포·읽기 전용 사후 확인한다. 로컬 생성기는 다음 명시적 예시부터 새 버전을 사용한다. 과거13단계/수정3회 시범을 재시작하거나 공개하지 않는다.

사람의 현재 원인 해결 요청을 이 구현에 적용한다. 부분 채택 방식 승인 요청은 철회하고 구현하지 않는다. 기존 API 복원 기준 studyez-api-release-1793757910362950700, 웹57fe6571-2415-4250-9895-e5f2bb903171은 변경 대상이 아니다. 원본·실패·사용량·검수 판정을 보존한다.
