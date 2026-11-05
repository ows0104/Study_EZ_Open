# 공통 뿌리 파이프라인 시간 초과 원인 분리 및 같은 수신 결과 재사용 — 구현 계획

## 변경 범위·대상 파일·순서
1. docs/changes/본작업의 probe.py로 짧은 합성 입력 A/B와 부분 실패 스트림을 관찰한다. 진단은 원래 강의/의학 출력으로 채택하지 않는다. 결과가 다른 원인을 가리키면 이 범위에서 관찰한 원인에 맞춰 계획 근거를 갱신한다.
진단 관측: minimal4.82초, 작은 AUTHOR34.46초/같은 JSON plain33.68초, 원래 큰 세션의 짧은 응답102.9초에 완료됐다. 실제 파일 protocol 합성 모델은96.6초/전체JSON11041bytes/최종응답98자로 완료되고 원래 의미 검증을 통과했다. 스키마 불능을 원인으로 단정하지 않으며 전체은행/지도 재출력 비용과 실패 진단 유실을 줄이는 계획된 file transport를 적용한다. 실제 같은 강의 개선 여부는 마지막까지 확인해야 한다.
2. runner/root_native_json.py에 공통 저작/원본 검수의 안전한 JSON 파일+작은 native 완료 영수증 transport와 실패 이벤트 보존을 구현한다. 원래 프롬프트/품질 원칙/전체 수용 스키마·컨텍스트·그림은 모델에 동일하게 전달하고 blind medical은 기존 호출을 유지한다. 새 production CLI와 runner/connection_generation.py의 /2 실행·게시 전 receipt 검사로 모든 강의의 같은 흐름에 적용한다. quizbank/공용 계약/native adapter 원본을 바꿔 생산자61f와 완료 캐시를 무효화하지 않는다. 별도의 실행 어댑터 SHA/수용 계약/입력 지문을 usage receipt로 명시한다.
3. runner/root_transport_recovery.py는 현 사용자 요청에 의한 같은 강의의 명시적 수정후1회 재사용만 처리한다. packet/자료/normalize/실패 이력/현재 source/model/session과 새로운 실행기 계약을 검사하고 원래 실패 ledger/세션/저널/미상 사용량을 먼저 보관한다. 새 transport가 낸 실제 AUTHOR 결과만 원래 모든 검사 후 generate 캐시에 채우며 교정1회는 유지한다. 실패 재호출은 하지 않는다.
4. 분리 검증 사본 tmp/rp5에 관련 파일/기록만 반영하고 검증·리뷰·로컬 적용 후 실제 같은 강의의 새 transport를1회 실행한다. 완료되면 기존 UI의 같은입력 재개로 source/medical/남은2회/개인 게시를 진행하고 실제 학습의 답 숨김→답만 보기→지도/집계를 확인한다. 자동전송/ChatGPT 직접 조작은 하지 않는다.
실제 관측 보완: 새 방식에서 generate180.799초/source299.255초/medical83.785초에 완료됐고 repair-1에서 공급자의 명시적 콘텐츠 제한으로 거절됐다. 공통 실행기에 시간 초과와 구별되는 거절 분류·원문 대신 짧은 UI 오류·진단 지문 보존·동일 입력 재호출/게시 차단을 추가한다. 실제 학습 화면 미완료를 성공으로 바꾸지 않는다. 새 테스트 test_root_content_restriction.py도 runner 검사에 포함한다. 추가 모델 요청 없이 기존 실제 거절 로그를 별도 보존·분류하고 기존 raw/실패 원장은 바꾸지 않는다.

## 검사 명령과 성공 조건
development.py verify의 contracts=pytest tests/contracts, llm=pytest tests/studyez_llm, runner=새 transport/recovery 테스트와 test_connection_generation/test_root_authoring_resume/test_root_session_resume, generator=pytest tests/quizbank/test_generation_pipeline_v2.py 및 test_initial_map_recovery_v2.py. 합성 CLI/파일 fixture로 실제 완료와 파일/영수증/입력/모델/원본/사용량 변조, 경로 탈출/링크/중복키/누락/큰파일/취소/실패 재실행 차단, 독립 blind 유지, 같은 생산자 캐시·최대3회 보존 및 게시 전 대조를 확인한다. 모델과 운영 API를 단위검사에 쓰지 않는다. 실제 진단/동일 강의 실행/학습 UI는 별도 관측 기록과 실제 화면으로 확인하고 합성 성공과 혼동하지 않는다.

## 위험·복원·승인할 범위
사용자의 현재 명시적 원인해결·공통구현·동일 수신 결과 재사용·학습 UI 검증 요청이 이 구체적 범위의 구현/로컬 적용/개인 시범 게시를 승인한다. 같은 허락은 재요청하지 않는다. API/웹 고정 산출물은 그대로이므로 추가 운영 배포는 하지 않는다. 복원은 /2 실행 진입점을 이전 quizbank CLI로 되돌리되 새 실패/출력/사용량/학습 사건은 보존한다. 새 실행 결과를 원래 실패로 덮어쓰거나 과거 콘텐츠를 직접 고치지 않는다. native 파일 저작도 실제 모델 작업 한 번이며 내용 수정/원본 대조/독립 검수 상한을 늘리지 않는다.
