# 다음 세션 인수인계 — StudyEZ Concept Tree 설계

## 사용자 목표
유지보수 토큰과 시간을 줄이도록 사이트(web/server), 출제(quizbank/quizgen/content), 연결(runner/bridge), 공용 계약(studyez_contracts)을 나누었다.
앞으로는 26필기와 족보에서 Concept Tree·족보 경향·출제 포인트를 독립적으로 추출하고, 문제를 만든 뒤 누락을 검증하며, 뿌리부터 탐색/여행하는 학습 구조를 설계하려 한다. 이번 세션에서는 아직 그 설계·구현을 시작하지 않았다.

## 먼저 읽을 곳
- 원본 프로젝트: C:/Users/ows01/Documents/Python Scripts/Study_EZ_Open
- 원본 AGENTS.md → CLAUDE.md → docs/map.md → docs/development/README.md.
- 최신 마감 결과: docs/changes/2026-10-26-site-closeout/results.md.
- 이 채팅 작업 폴더: C:/Users/ows01/Documents/Codex/2026-10-26/wlr.
- 사용자 보고서: outputs/studyez-refactor/closeout-report.md 및 production-release-report.md. 전자가 이번 세션의 최신 보충 기록이다.
큰 work/tmp/runs·원본 자료 전체를 다시 읽지 말고 관련 경로만 읽는다.

## 현재 상태
운영 API studyez-api-00171-9wx(100%), 웹91dcddba-bb83-43b7-94a8-a50fc75d4d43는 앞선 세션에서 배포 완료했다.
이번에는 실제 운영 세션 복원·목록79문항·정답/해설·학습 시작화면·개념43개·상태 수동/자동 갱신을 확인했다.
갱신 GET13건200. 현재 정상이나 과거 갱신 실패 원인은 미확정이다. 이미 해결한 원인으로 꾸며 쓰지 않는다.
새 로그인 입력 왕복과 운영 채점 저장/되돌리기는 미검증이다. 사용자 데이터 보존을 위해 운영 채점을 하지 않았으며 격리된 DB의 관련 검사5파일은 통과했다.

배포 도구는 server/deploy.ps1 + server/deploy-revision.ps1로 보완했다. 고유 revision 생성→정확한 준비/생성 확인→명시100전환→최종일치 순서다. 기본 GatePython 경로 오류도 수정했다.
tests/development 전체31개(그 안에 새 전용2개 포함), 가짜클라우드12상황 통과. 새 도구의 실클라우드 배포는 아직 실행하지 않았다. 다음 실제 배포 때 기존 결과를 재사용하지 말고 새 소스·설계·후보에 맞는 승인/검사 절차를 수행한다.
기존 production-* 작업의 검사/후보는 당시 소스의 역사적 증거다. 로컬 도구가 바뀌어 지문이 달라졌으므로 다음 배포에 그대로 재사용할 수 없다.
관련 코드 수정과 기록을 원본에 반영했다. 새 운영 앱 배포·커밋·푸시는 하지 않았다. 기존 미커밋 변경이 많으므로 되돌리거나 섞지 않는다.

## 다음 작업 방법
사용자의 최신 지시를 확인하고 Concept Tree의 Plan·Design부터 진행한다. 먼저 학습자 여정·개념 단위/관계·근거 연결·추출 산출물 간 독립성·출제 포인트 연결·누락 검증·기존 문항/학습 기록 호환성·완료 기준을 구체화한다.
기존 개념 지도가 있다는 이유로 이를 곧바로 새 Tree 정본으로 삼지 않는다. 26필기/족보의 역할과 독립 추출 기준을 먼저 정한다.
정책·문항·학습 기록을 임의로 바꾸거나 강의를 재출제하지 않는다. 기존 제외·검수 횟수·원본·ID·학습 기록 보존 규칙을 따른다.
모든 새 작업은 docs/changes/<id>/intent.md → spec.md → plan.md로 기록하고 실제 사용자의 구현 승인 후 Build/Test, 중요 배포 승인 후 Deploy/Maintain으로 연결한다. Concept Tree 구현/배포의 포괄 승인은 아직 없다.
