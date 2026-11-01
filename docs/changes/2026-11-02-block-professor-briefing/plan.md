# 블록 시작 교수 변경 안내와 교수별 기출 스타일 — Implementation Plan

상태: 문서화 단계의 구현 계획 초안. 현재 요청의 실행 범위는 문서 작성·연결·문서 확인이다.
Build·실제 기출 분석·자료 업로드·운영 DB 변경·배포는 실행하지 않았다. 아래는 후속 구현 계획이다.

## 1. 구현 전 결정과 원본 조사

1. P10의 비교 기준·노출 시점·첫 적용 블록·표본/검토 기준·갱신/공개 방식을 정하고 Spec을 갱신한다.
2. 승인 대상 블록의 시간표, 연도별 교수 이력, 올해 실제 필기 담당, 기출 관리 자료의 실제 경로·판·강의 대응만 조사한다. 현재 문서 작업에서 runs/work/tmp·강의 원본을 탐색하거나 분석하지 않는다.
3. 데이터 예시와 API·저장·공개·실패 계약, 확정 파일 목록과 검사 명령을 보완한다. 현행 사용자 지시와 보존 정책을 반영한 구체 계획에 사람의 구현 승인을 기록하고 `scripts/development.py check --phase build`를 통과한 뒤 Build한다.

## 2. 변경 파일·구현 순서 후보

| 순서 | 대상 후보 | 역할 |
|---|---|---|
| 1 | `studyez_contracts/professor_briefing.py`(신규 후보), `tests/contracts/` | 담당 출처·비교·스타일·집계·입력 판·검토 상태의 공통 계약. 생산자/소비자 함께 검증 |
| 2 | `runner/professor_briefing.py`(신규 후보), `runner/matching.py`·`runner/blocks.py`의 기존 읽기 기능 | 승인된 범위의 자료로 강의/교수 대응과 변경 판정, 근거 있는 스타일 초안 생성. CLI 연결 위치·분석 실행 방식은 승인 전에 확정. 기존 매칭 정책은 임의 변경하지 않음 |
| 3 | `server/app/models/professor_briefing.py`·`server/app/routes/professor_briefing.py`(신규 후보), 모델/라우트 등록부, `server/app/cli.py` | 결과 판·검토/게시 저장, 학생 조회/관리자 게시 권한 분리. 서버는 runner/생성기를 import하지 않음. 새 DB 구조는 격리 환경에서 검증 |
| 4 | `web/src/types/professorBriefing.ts`·`web/src/bank/ProfessorBriefing.tsx`(신규 후보), `web/src/api.ts`, `web/src/bank/StudyOverview.tsx`, `web/src/calendar/EventPanel.tsx` | 블록 요약·변경 강의 목록·교수별 스타일·근거 진입. 기존 `studyBlocks.ts`/`useStudyCourse.ts`의 블록 선택 정책을 재사용하며 새 분석 정책을 웹에 복제하지 않음 |
| 5 | `web/src/notices/GuidePage.tsx`, `server/app/usage_actions.py`·`server/app/routes/usage.py`, 관련 서버 검사 | 사용법과 열람/근거 열기 등 채택한 행동을 이용현황 공통 카탈로그에 함께 등록. 실제 열람·학습 완료로 과장하지 않음. 행동/저장 방식은 구현 전 확정 |
| 6 | 관련 테스트, 이 작업의 `release.md` | 수용 기준 검증, 리뷰·고정 후보·승인·사후 확인 준비 |

파일은 설계 후보이며 생성된 구현 파일이 아니다. P10 결정에 따라 이 목록을 갱신하고 공유 워크스페이스의 다른 변경을 섞지 않는다.
실제 기출 분석 방식·도구·입력 전달·검토 책임도 승인 범위에 포함한다. 자동 모델 호출·기존 출제 경로 변경을 현재 문서 요청에서 추론하지 않는다.

## 3. 검사 계획과 state.json 대응

아래 `required_checks`는 후속 Build의 필수 검사 목록이다. 현재 실행·통과한 검사 근거가 아니다.

| 체크 이름 | 예정 검사와 성공 조건 |
|---|---|
| professor-analysis | 신규 `tests/runner/test_professor_briefing.py` 후보를 프로젝트 Python의 pytest로 실행. 직전 연도 누락·공동 담당 변경·별칭/동명이인·분반/합본·출처 충돌·중복/재출제·교수 미상·이미지 확인·표본 부족·오래된 판을 검증 |
| contracts | 프로젝트 Python으로 `-m pytest tests/contracts -q`. 교수별 분석 생산자/소비자의 스키마·출처·판·불확실성 계약 검증 |
| server | 격리 DB/저장소를 명시하고 server에서 `.venv/Scripts/python.exe -m tests professor_briefing`, `-m tests route_contract`, `-m tests usage_actions`, `-m tests usage`를 각각 실행하는 검사 묶음. 권한·학생 비노출·검토/공개·폐기·갱신·실패와 행동 등록 검증 |
| web | `npm.cmd --prefix web run typecheck` 및 `npm.cmd --prefix web run build`. 블록 선택 회귀(`node --test web/tests/study-blocks.test.cjs`)와 신규 안내 컴포넌트 검사를 포함하는 검사 묶음 |
| browser | 계정/API 없는 격리 자료로 첫 블록 진입·재열기·다른 블록 선택·필기 도착 후 갱신·자료 없음/실패·근거 열기·좁은 화면·키보드 탐색 확인. 검토한 기출 사례의 원본/이미지와 요약 대응을 별도 수동 대조 |

여러 명령의 검사 묶음은 모든 결과를 보존하는 실행기로 확정한 후 `development.py verify`에 연결한다.
state의 area는 공통 계약 변경 범위인 `contracts`로 설정한다. `scripts/workflow_scope.py`에서 이 영역은 site·integration 등을 함께 지문화하므로 runner 생산자와 서버/웹 소비자의 변경을 검사 근거에 포함한다.
Test 후 `review`, `check --phase release`에 실제 결과를 결합한다. 미실행·자료 부족·실패를 통과로 남기지 않는다.

## 4. 보존·위험·복원과 Release/Maintain

- 오귀속·비교 연도 착각·적은 표본의 일반화·중복 집계·이미지 누락을 핵심 검토 대상으로 삼는다. 근거 없는 교수 평가나 올해 출제 확률은 만들지 않는다.
- 기존 문제은행·첨부·학습/검수 기록은 읽기 자료로 보존한다. 교수 구성 변경을 이유로 기존 은행이나 기출을 삭제하지 않는다.
- 결과를 독립 판으로 저장하고 이전 공개 판을 보존해 공개 취소 또는 이전 검토 판으로 복원한다. 기능 오류 시 안내만 비공개 처리할 수 있게 설계하고 기존 학습 진입은 유지한다.
- 운영 DB 구조·게시 범위·배포는 구체 후보의 중요 승인 후 진행한다. DB/API 준비와 기존 웹 호환을 먼저 검증하고 웹을 배포한다. 롤백은 기존 DB 자료를 삭제하지 않는 순서로 준비한다.
- Maintain에서는 시간표·실제 필기 담당·원본 기출 판 변경을 감지할 책임과 실행 주기를 확정한다. 관련 분석만 재검토 대상으로 만들고 반복 실행·재알림으로 결과나 기록을 덮어쓰지 않는다. 별도 예약 자동화는 요청 전 생성하지 않는다.
