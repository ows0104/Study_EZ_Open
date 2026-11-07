# 감염병리1 Map 파이프라인 재구성 — 설계

## 요구사항과 수용 기준
1. Map 추출(`content/prompts/learning-links/map-extract.md` → concept-map-extract/3): 참고판(map-extract-reference.md)의 트리 지시를 본문으로 쓰고, concepts[].parent_id(최상위는 null)를 추가한다. 수용: 모든 parent_id가 존재하는 개념, 순환 없음, 최상위 1~8개, 깊이 2 이상 개념 존재, 관계는 부모-자식 외 교차 연결 포함. 이전 /2 결과·프롬프트는 버전으로 보존(읽기 호환).
2. 포인트 추출: 기존 point-extract.md와 정제(point_refinement) 흐름을 그대로 쓴다.
3. 생성(root-generation/2, `runner.root_native_json`): packet.conceptMap에 /3 Map을 넣는다. 정규화 수용에 "Map 개념 ID의 parent_ids가 Map parent_id와 같다"는 검사를 추가한다. 어긋나면 기존 규칙대로 초기 지도 오류로 첫 정리에 전달(보완 1회 소비)하고 원문을 보존한다. extract-v2.md에 같은 보존 지시를 한 줄 추가한다.
4. 구조 문제: 기존 author-v2 흐름의 root/branch target이 Map 관계를 근거로 생성된다. 최종 문서 집계(개념 계층 깊이, 관계 종류, target 역할)를 결과 보고에 남긴다.
5. 화면: 이미 배포된 트리 지도(PR #19)가 parent_ids를 그대로 그린다. 구조 문제가 교차 연결에 걸린 경우를 지도에서 확인한다(부족하면 별도 UI 작업으로 분리).

## 책임·입출력 계약·오류 상태
- 실행 폴더: 메인 체크아웃 `runs/_e2e/<id>`(짧은 경로). 원본·Map·포인트·packet·ledger·모델 원문/사용량·실패를 보존한다. 실패한 호출은 자동 재시도하지 않는다.
- 결정적 검사는 모델 없이: Map/포인트 형식·계층 검증, packet 지문, 결과 validate_result.
- 운영 DB·R2·학습 기록 미사용. 격리 SQLite/로컬 저장소로만 풀이 확인.

## 호환성과 데이터 보존
현 공개 판(main-quiz-reviewed-6143c8c89ad64d9c)·기존 은행·학습 기록 불변. /2 Map 결과와 E2E 실험 산출물 불변. 새 판은 운영에 등록할 때 새 revision으로만 추가하고 기존 판을 지우지 않는다(별도 승인).
