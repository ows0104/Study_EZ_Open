# 감염병리1 Map 파이프라인 재구성 — 구현 계획

## 변경 범위·대상 파일·순서
0. 브랜치 claude/infection-path1-map = origin/master + codex/map-point-prompts·map-flow-reference·map-point-e2e(충돌 없이 병합, 승계).
1. 프롬프트: map-extract.md를 /3(트리 지시+parent_id)로, 스키마·예시 갱신, /2 사본 보존. extract-v2.md에 Map 부모 보존 한 줄.
2. 계약/엔진: Map /3 형식 검증(존재·순환·최상위 수) 함수와 정규화 후 부모 보존 검사(초기 지도 오류로 연결). 합성 단위 검사 추가.
3. 실행 도구: 이 폴더에 감염병리1용 prepare/map/point/refine/packet/verify 스크립트(기존 pilot_extract.py·point_refinement.py·experiment.py에서 하드코딩 값만 바꾼 사본)와 결과 집계.
4. 실행(승인 후, 하위 프로세스 Codex CLI gpt-6.1-sol, 백그라운드):
   a. Map 1회 + 포인트 1회 추출(원본 S1·S2만 입력) → 형식·계층 검증.
   b. 포인트 정제(추출→대조→보완→재대조, 모델 4회).
   c. root-generation/2: 정규화 → 출제 → 원본 대조·독립 정답 검수, 보완 최대 3회.
5. 격리 로컬 등록·풀이 화면에서 트리·구조 문제 확인, 결과 집계·문제 품질 보고.

## 검사 명령과 성공 조건
- contracts: 새 Map 검증·부모 보존 검사 단위 테스트 + 기존 roots/learning-links 계약 테스트(pytest tests/contracts 관련 파일, tests/quizbank/test_connection_generate*).
- generation: 실행 결과 validate_result 통과, Map 계층(최상위 ≤8, 깊이 ≥2)과 정규화 보존, 관계 종류 ≥3, root/branch target 존재, 검수 기록 보존.
- 화면: 격리 로컬에서 지도 트리 다층 표시·구조 문제 풀이·평가 저장 확인(학습 쓰기는 격리 DB만).

## 위험·복원·승인할 범위
승인 요청 1(구현): 위 1~3의 코드·프롬프트 변경과 로컬 검사.
승인 요청 2(외부 전송·생성): S1 필기(sha 4b4229bc…, 37쪽)·S2 족보(sha 82ba65c6…, 27쪽)의 텍스트·페이지 이미지를 OpenAI Codex CLI(gpt-6.1-sol)로 보내 Map·포인트 추출, 파생 결과(Map·포인트·대조 결과)의 후속 전송과 정제 보완 1회·재대조 1회, 문제 생성·원본 대조·독립 정답 검수와 최대 3회 보완.
비포함: 운영 등록·공개·master 병합(별도 승인). 실패는 자동 재시도하지 않고 원문·ledger를 보존하며, 상한 도달 시 보류로 보고한다. 복원: 브랜치·실행 폴더만 남고 운영 변경 없음.
