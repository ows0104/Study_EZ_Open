# 구현·실행 계획

1. 정확한 고정 입력과 원장/기존 단계 지문을 검사하는 example_run.py를 이 기록 폴더에 작성한다. --preflight는 모델을 호출하지 않는다. 테스트/배포를 마친 tmp/root-web의 생성기·순수 compiler를 사용한다.
2. 사용자 현재 승인을 기록하고 --preflight를 development.py verify로 확인한다. --run은 새 runs/_examples/cholinergic-20261104 폴더만 만들며 기존 폴더가 있으면 중단한다. source1회 시작을 원장에 먼저 기록한다. g.prepare/g.call_model과 compile_source_assessment/make_document를 실제 호출한다. BANK 변경/repair/새 독립 정답 모델 호출/운영 게시 기능은 넣지 않는다.
3. --check-result를 verify로 실행해 재조립 결과·raw/usage/hash·구조/전수 검사·문항 보존·재사용 medical provenance·원래 원장 보존을 확인한다. 실제 내용과 남은 지적을 검토하고 release.md에 예시 완료/미게시와 한계를 남긴다.
4. 생성된 실제 문항·목표·연결·미준비·검수 지적을 읽기 전용 미리보기로 보여 준다. 새 문항/정답/의학 설명은 부모가 작성하지 않는다. 필요하면 읽기 전용 결과 JSON도 제공한다.

현재 사용자의 자료 기반1회 실행 요청으로 이 구체적 범위를 승인한 것으로 기록한다. 중요 운영 배포는 이번 범위에 없다. 기존 생성기/서버를 수정할 필요가 생기면 같은 원인 해결 범위에서 먼저 기록하고 검증하며, 기존 산출물/모델 호출은 보존한다.

실제 source1회가 완료된 뒤 P13의 requirement=undecided/직접회상확인 조합이 기존 compiler에서 표현되지 않아 조립만 실패했다. 원문/사용량/첫 실패 원장은 그대로 보존하고, 2026-11-04-coverage-requirement의 검증된 순수 규칙으로 assemble_result.py --assemble(추가 모델0회)을 실행한다. example-result 체크는 assemble_result.py --check로 원문/runtime 계보/문항/판정 보존 및 재조립을 검증한다. 원래 example_run.py와 실패 원장을 성공으로 덮어쓰지 않는다.
