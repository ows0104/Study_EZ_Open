# StudyEZ 현황 조사와 근거

조사일: 2026-10-26 (Asia/Seoul)
읽은 프로젝트: `C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open`
방법: 로컬 문서·코드·설정 읽기, 제한된 소스 경로 검색, 기존 피드백 개선 채팅의 최근 상태 확인.

## 관찰 결과

| 관찰 | 확인한 위치 | 해석 |
|---|---|---|
| 컴포넌트 안내·작업 지도·파일 계약이 이미 있음 | CLAUDE.md, docs/map.md, docs/artifact-contract.md | 기존 구조를 바탕으로 경계와 읽기 범위를 개선할 수 있음 |
| 출제기가 웹 프롬프트를 직접 읽음 | quizbank/generate.py:15~16, priority_only.py:54 | 출제 자산 소유권과 패키징 경계 개선 대상 |
| 출제기가 서버의 공유 검증 모듈을 직접 import | quizbank/schema.py, validate.py, compact.py, run.py 등 | 검증은 이미 재사용 중. 중복 구현보다 공용 패키지 추출이 적합 |
| 웹 빌드가 확장 ZIP과 프롬프트 JSON 생성 | web/package.json, web/scripts/pack-extension.mjs | 확장을 단순 보관하면 웹 빌드/배포가 깨질 수 있음 |
| 은행 라우트에 여러 책임이 모임 | server/app/routes/bank.py | URL 보존 아래 내부 분리 후보 |
| 포인트 추출/누락 검사 구현이 이미 있음 | quizbank/points.py, coverage.py | 새로운 출제 단계와 비교해서 재사용할 기반 |
| 개념 지도·학습 엔진이 이미 있음 | web/src/bank/ConceptMap.tsx, server/app/study_engine/ | 새 여행형 학습의 출발점, 현행 정책과 새 정책은 구분 필요 |
| Spotter가 서버에 등록되고 인증/DB를 공유 | server/app/main.py, docs/architecture.md, docs/deployment.md | 독립 제품이지만 현재 실행 의존성까지 독립인 것은 아님 |
| work 아래 작업 폴더가 157개 존재 | work의 바로 아래 디렉터리 수 | 전체 검색에 release 사본이 다수 나타남. 157개 전부 불필요하다는 뜻은 아님 |
| 검색 제외가 일부 생성물/기록에만 적용 | .ignore | work/tmp 등으로 검색 범위를 더 정리할 여지 |
| 루트 안내에 강의별 과거 지시가 다수 누적 | CLAUDE.md | 활성 제약 색인과 작업 이력의 구분이 필요 |
| 학습 기록 보존 정책이 이미 중요하게 다뤄짐 | server/CLAUDE.md, bank_retention.py, study_retention.py | 구조 정리·재출제에서 반드시 승계해야 하는 조건 |
| runs에 사람의 선택·메모·수동 원문 등이 존재할 수 있음 | docs/runs-layout.md, runner/CLAUDE.md | 통째로 캐시로 간주해 이동·삭제하면 안 됨 |
| 매시간 피드백 수집·분석 루프가 문서화되어 있고 최근 실행 기록이 있음 | docs/feedback-loop.md, “사이트 피드백 개선 루프 만들기” 채팅 | Maintain의 일부 기반이 있음. 모든 장애 감지가 갖춰졌다는 뜻은 아님 |

## 크기 측정 참고

아래 값은 현재 로컬 파일 중 `.py/.ts/.tsx/.md`에 대해 PowerShell `Measure-Object -Line`으로 측정한 줄 수다. 빈 줄이 제외되는 방식이며 순수 코드 줄 수나 토큰 수가 아니다. 저장소 전체 크기 또는 실제 운영 버전 크기를 뜻하지 않는다.

| 경로 | 해당 파일 수 | 측정 줄 수 |
|---|---:|---:|
| web/src | 138 | 15,288 |
| server/app | 104 | 13,149 |
| quizbank | 49 | 4,150 |
| quizgen | 63 | 12,403 |
| runner | 42 | 9,402 |
| studyez_llm | 5 | 321 |

대표 큰 파일: server/app/routes/bank.py 1,892줄, quizgen/jokbo.py 1,511줄, runner/agent.py 1,051줄. 크기는 분리의 단독 근거가 아니며 실제 책임과 변경 이유로 나눈다.

## 추가로 확인해야 할 것

- 로컬 Git HEAD 읽기 결과는 `e33b14279d9510c1eed7765e871f4766404738b1` (2026-10-19, Require verified Markdown bank files for all lectures).
- Git status는 “must be run in a work tree” 및 명시 경로 시 권한 관련 오류로 성공하지 못했다. 저장소 손상으로 단정하지 않았고 Git 설정을 바꾸지 않았다. 미커밋 변경, 원격과의 일치, clean 상태는 확인되지 않았다.
- 현재 운영 웹/API/러너 revision은 확인하지 않았다. 작업 사본에 더 최근 변경이 있을 수 있으므로 로컬 루트만으로 운영 정본을 확정할 수 없다.
- README의 Main 생성/자동 공개 설명과 architecture의 현재 방식 설명에 차이가 있다. 실제 코드와 운영 설정을 대조해서 현재 설명으로 정리해야 한다.
- 실제 사용하지 않는 파일, 실행 중인 작업 사본, 복원 가능한 보관 목적지는 아직 확정하지 않았다.
- 테스트 실행·사이트 동작 검증·운영 DB 접근·출제·파일 이동·배포·자동화 수정은 수행하지 않았다.

## 이번 결과

분석을 바탕으로 intent.md, spec.md, plan.md를 작성했다. 운영 변경 없이 승인할 수 있는 첫 구현 범위를 P0~P2로 제안했다. 새 출제 정책과 학습 여행의 상세 규칙은 미정으로 표시했다.
