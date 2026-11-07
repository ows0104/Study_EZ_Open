# Implementation Plan

1. `web/src/lecture/reviewPrompt.ts`의 기본 문장만 요청 원문으로 교체한다.
2. `web/src/lecture/reviewProfessor.ts`의 교수 안내를 한 줄로 축약한다. 기존 파일명 파싱은 유지한다.
3. `web/tests/review-professor.test.cjs`의 출력 기대값과 예시·공동 교수 검사를 갱신한다. 기존 은행 규칙 검사에서 이미 사라진 1.79 버전·문구 고정 대신 현재 교수 정보 자리표시자와 우선/참고 계약을 확인한다. 은행 프롬프트는 수정하지 않는다.
4. `review-prompt`: 해당 Node 검사. `web`: 타입 검사와 정식 웹 빌드. 실제 실행 결과를 development.py로 기록하고 직접 diff를 리뷰한다.
5. 일반 코드 PR/자동 배포 절차를 따른다. DB·운영 자료·학습 기록 변경은 없다. 복원은 이 수정 커밋을 되돌리는 별도 PR로 한다.

위 범위는 2026-11-07 현재 채팅의 사용자 명시 수정 요청으로 승인되었다. 같은 범위의 승인을 다시 요청하지 않는다.
