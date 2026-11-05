# 예습 cloze 표시를 복습 Quiz Bank 방식에 맞추기 — 구현 계획

## 변경 범위·대상 파일·순서
1. 사람 승인 후 development.py approve/check --phase build로 현재 문서에 묶인 승인 근거를 기록·검사한다.
2. server/app/quiz_cloze.py(신규)에 서버용 순수 파서를 두고, routes/prequiz.py의 예습 reveal/undo 및 missed/extraMissed 응답에 검증된 clozeParts를 추가한다. 기존 cards.py의 source_stem 가림 규칙과 호환성을 검사한다.
3. web/src/types/quiz.ts에 선택적 응답 타입을 추가한다. web/src/lecture/PreQuizCloze.tsx(신규)에서 풀이 전에는 기존 PreQuizText를 그대로 사용하고, 답 공개 후에만 원문 조각의 빈칸 답을 강조해 렌더링한다. 기존 PreQuizText의 문장 여백·강조를 보존하고 base.css에서 복습 Quiz Bank와 같은 정답 색과 강조를 적용한다.
4. PreQuiz.tsx와 PreQuizDifficult.tsx에 적용한다. basic/OX, 힌트·설명·답 단락·이해 확인·되돌리기는 기존 동작을 유지한다. GuidePage.tsx의 예습 안내에 문장 속 빈칸 공개 방식을 짧게 반영한다.
5. web/tests/prequiz-cloze.test.cjs, server/tests/test_prequiz_cloze.py를 추가하고 web/tests/prequiz.tsx의 메모리 예시에 cloze를 추가한다. 검사 후 변경 코드 리뷰와 release.md를 준비한다.

## 검사 명령과 성공 조건
아래 검사는 구현 승인 후 development.py verify로 실제 실행하며 해당 이름으로 근거를 저장한다.
- web-cloze: node --test web/tests/prequiz-cloze.test.cjs web/tests/stem-artifacts.test.cjs. 풀이 전 기존 표시·힌트·복수 빈칸 순서·여러 줄·강조·미공개 정답 부재·공개 시 정확한 위치·원문 없는 카드의 기존 표시를 검증한다.
- web-typecheck: npm --prefix web run typecheck.
- web: npm --prefix web run build.
- server: server/에서 .venv/Scripts/python.exe -m tests prequiz_cloze. 격리된 로컬 DB/저장소를 명시한 테스트에서 초기 목록/슬라이드 API 정답 비노출, reveal/undo 위치 정보, 원문 없음/불일치 시 fallback, basic/OX/mainquiz의 기존 계약을 확인한다.
  server 검사에는 기존 회귀도 포함한다: 각 필터별로 server/에서 .venv/Scripts/python.exe -m tests prequiz_once, -m tests quiz_kinds, -m tests route_contract를 독립 실행한다. 파일마다 독립 실행하는 기존 검사기를 따른다.
메모리 API 예시 화면에서 최초 공개→다음 문항→되돌리기→완료 목록을 확인한다. UI 실행 도구가 없으면 실제 확인하지 못한 항목을 release.md에 명시한다. 운영 DB는 검사에 사용하지 않는다.

## 위험·복원·승인할 범위
승인 요청 범위는 위 답 공개 후 예습 cloze 표시·어려웠던 문제 적용·선택적 reveal/missed 계약·로컬 검사와 리뷰 준비까지다. 운영 배포는 고정 후보·검사·release.md 준비 후 별도 중요 승인으로 진행한다.
핵심 위험은 초기 정답 노출과 여러 빈칸의 잘못된 위치 매핑이다. 원문은 reveal 이후에만 전달하고, 현재 stem과의 일치 확인 및 기존 표시 fallback으로 대응한다.
문항·기록·DB는 건드리지 않는다. 복원은 이 작업의 웹/서버 코드 변경만 되돌린다. 기존 미커밋 변경과 다른 작업 문서는 포함하지 않는다.

## 2026-11-02 운영 배포 승인 적용
사용자: “운영 사이트에도 배포해줘.” 기존 구현 범위 그대로 서버→웹 운영 반영을 승인했다. 동일 범위의 승인을 다시 요청하지 않는다. 배포 필수 체크명 web/server/contracts로 근거를 정리하며, contracts는 루트 .venv/Scripts/python.exe -m pytest tests/contracts -q로 실제 실행한다. 서버 체크는 prequiz_cloze/prequiz_once/quiz_kinds/route_contract를 각기 독립 실행한다. web은 check_web_release.py로 운영 빌드 및 로컬 검사 인증정보 비포함도 확인한다. 소스와 사용자 기능 범위는 확대하지 않는다. 고정 서버/웹 후보를 순서대로 준비·승인 기록·배포하며 각 영수증을 보존한다. 설정 파일과 사후 검사 도구는 이 변경 폴더에 보관한다.
