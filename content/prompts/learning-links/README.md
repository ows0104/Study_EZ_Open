# 연결 검토 묶음 v1

원본 기반 개념도·포인트와 실제 문항의 연결을 **별도 로컬 검토 묶음**으로 보관한다. 기존 문제은행·검수·사용자 기록은 변경하지 않는다. 자동 생성·모델 호출·웹 전송·서버 게시 기능은 없다.

## 원본 전용 추출 요청문

- [Map 추출](map-extract.md): 필기·족보의 개념·분류·관계·큰 흐름만 구성한다. 문항 대응·누락 판단·문항 학습 순서는 이후 대조 단계에서 다룬다.
- [독립 출제포인트 추출](point-extract.md): 이전 points 지침의 목표 묶기·원본 근거·전체 범위 확인에 연결 회상 철학을 적용한다.

각 요청에 동일한 원본 필기·족보와 해당 강의 범위만 별도로 제공한다. Map 결과를 포인트 추출의 범위 기준으로 넣지 않는다.

| 결과 | 버전 | 스키마 | 완전한 합성 예시 |
|---|---|---|---|
| Map | concept-map-extract/1 | [map-output.schema.json](map-output.schema.json) | [map-output.example.json](map-output.example.json) |
| 포인트 | exam-point-extract/1 | [point-output.schema.json](point-output.schema.json) | [point-output.example.json](point-output.example.json) |

두 프롬프트는 최종 JSON 객체 하나를 요구한다. Map의 sections는 표시용 묶음이며 concepts/relations가 실제 그래프다. 포인트는 groups/points/directions로 목표와 필요한 회상을 구별한다. 각 결과 안에서 고유한 ID를 사용하며 서로의 ID 대응은 후속 대조에서 결정한다. extracted/partial/unreadable은 자료 확인 범위에 대한 기록이며 정확성 인증이 아니다.

JSON Schema는 타입·필수 필드·열거값을 검사한다. 결과 안의 참조·ID 중복·분류 순환·실제 쪽수 범위 등은 추가 검사가 필요하다. 개발 기록의 [verify_formats.py](../../../docs/changes/2026-11-06-map-point-prompts/verify_formats.py)는 합성 정상/오류 사례와 프롬프트 내 예시를 검증한다. 자료와 실제 추출 결과의 의미는 별도 원본 검토가 필요하다.

현재 자동 생성기에 연결되지 않았다. 현행 자동 파이프라인은 여전히 automation/extract-v2.md로 Map·포인트를 함께 추출한다. 기존 learning-brief/2나 quizbank/prompts/points.md의 PLAN 출력을 이 형식으로 대체하지 않는다. 실제 응답 수신·저장·화면 렌더링·호출 분리·후속 대조의 연동은 별도 구현 범위다.

## 입력과 실행

저장소 루트에서 프로젝트 Python을 사용한다. `<...>`는 실제 경로로 바꾼다. 출력은 아직 존재하지 않는 폴더여야 한다.

```powershell
.\.venv\Scripts\python.exe -m quizbank.connection_plan --review <review.json> --bank <bank.json> --sources <sources.json> --out <새폴더>
```

- `review.json`: 허용된 작성/검토 경로에서 만든 `REVIEW_SCHEMA` 형식의 결과. 의미 판단을 코드가 대신 만들지 않는다.
- `bank.json`: 명시적으로 선택한 은행 판. 최소 `questions` 배열, 고유 `question_id`, 비어 있지 않은 `question`/`answer`가 필요하다. 나머지 기존 문항 필드·검수 상태도 지문과 보고서에 보존된다. 이 도구의 최소 입력 검사는 기존 은행의 전체 스키마/의학 검수를 대체하지 않는다.
- `sources.json`: 읽기를 허용한 원본 파일의 명시적 목록. 상대 경로는 이 JSON이 있는 폴더 기준이다. 외부 URL은 내려받지 않는다.

```json
{
  "schema_version": "learning-link-sources/1",
  "sources": [
    {"source_id": "S1", "path": "lecture.pdf", "sha256": "실제 파일의 소문자 SHA256 64자리"}
  ]
}
```

원본 해시는 원본 바이트의 SHA256이다. `bank_sha256`은 은행 파일 바이트의 SHA256이다. 문항 지문은 `studyez_contracts.learning_links.question_hash(question, bank)`로 계산한다. 문항 전체와 questions를 제외한 은행 문맥을 포함하며 JSON 객체 키 순서만 정규화한다. 문자열 공백/배열 순서/선지·짝/출처/검수/개인 수정 변경은 보수적으로 재검토 대상으로 본다. 지문을 새 값으로 바꾸는 것만으로 이전 의미 검토가 새 판에 유효해지지 않는다.

기계가 읽는 정본은 `studyez_contracts.learning_links.REVIEW_SCHEMA`, `SOURCES_SCHEMA`다. 아래는 계약 조회 예시이며 새 의미 결과를 생성하지 않는다.

```python
import json
from studyez_contracts.learning_links import REVIEW_SCHEMA
print(json.dumps(REVIEW_SCHEMA, ensure_ascii=False, indent=2))
```

## review.json의 구조

모든 필드는 필수다. 해당 내용이 없으면 계약이 허용하는 빈 배열/명시적 null/미확인 상태를 쓴다. 임의 필드나 중복 JSON 키는 거절된다. ID는 묶음 내 안정적인 식별자이며 예전 트리·포인트 ID나 개수에 묶이지 않는다. 기존 결과를 갈아엎을 때 새 원본 기반 검토와 판을 만들고 옛 묶음은 보존한다.

| 필드 | 내용 |
|---|---|
| schema_version / hash_policy | `learning-links/1` / `learning-links-question/1` |
| lecture_id / bank_sha256 | 강의 식별자 / 검토한 은행 파일 지문 |
| scope | label, included, excluded, reviewed, limitations, outside_list_review. 실제 범위/검토/목록 밖 누락 검토의 한계를 표시 |
| provenance | status(draft/reviewed), method, reviewer, independent_points(confirmed/unverified/derived), notes. 입력의 주장이지 도구 인증이 아님 |
| sources | source_id, label, sha256, kind(lecture/notes/exam/other), professor, year, page_count. 미상은 null |
| concepts | concept_id, label, parent_ids. 같은 목표가 여러 위치를 참조할 수 있음 |
| relations | relation_id, from_id, to_id, kind, condition, evidence, review_status(reviewed/unreviewed), reason |
| targets | target_id, title, concept_ids, relation_ids, role(root/branch/leaf), reason, evidence, directions, importance |
| points | point_id, text, evidence, target_ids, scope_status(included/excluded), reason. 원본 독립 추출 근거를 provenance에 보존 |
| mappings | question_id, question_sha256, target_id, direction_id, tested_relation_ids, provided_relation_ids, explanation_relation_ids, reason |
| coverage | point_id, status, confirmed_direction_ids, partial_direction_ids, missing_direction_ids, unknown_direction_ids, reason, exclusion_basis |

`evidence` 및 `refs` 항목은 `{source_id, locator, pages}`다. pages는 **해당 원본의 물리 쪽**이며 locator로 문항 번호·단락 등 다른 위치 체계를 함께 보존한다. 페이지를 쓸 때 source의 page_count가 있어야 한다. page_count는 입력 선언이며 이 도구는 PDF 지면을 해석하거나 실제 쪽수를 인증하지 않는다. 페이지를 모르면 pages를 비우고 실제 식별 가능한 locator와 한계를 남긴다.

관계 kind는 classification/causal/comparison/sequence/prerequisite/association이다. classification과 명시적 prerequisite의 순환, 개념 parent_ids 순환은 거절한다. 비교·인과·상호 관계를 모두 선수관계로 해석하지 않는다. 목표 없는 관계도 보고서에서 따로 보이며 사라지지 않는다.

directions는 `{direction_id, cue, answer_scope, requirement, relation_ids}`다. requirement는 required/optional/undecided이며 direction_id는 묶음 전체에서 고유하다. 같은 목표의 모든 relation_ids를 하나 이상 방향이 다뤄야 한다.

importance는 structural/exam/clinical 각각 `{status, reason, evidence}`다. status는 supported/insufficient/unreviewed다. evidence 항목은 `{kind, reason, refs}`이며 supported는 최소 한 근거가 필요하다.

- structural: `structural_rationale`
- exam: `observed_exam`, `exam_forecast`, `teaching_emphasis`
- clinical: `clinical_rationale`

관찰한 출제·올해 예측·임상 판단을 혼합하거나 자료 부족을 점수 0으로 만들지 않는다. supported는 작성자의 근거 있는 주장이고 자동 의학 인증이 아니다. 단일 중요도 점수/Tier는 생성하지 않는다.

## 대조 판정

포인트마다 coverage가 정확히 하나 있어야 한다. 해당 포인트의 모든 목표/방향을 확인/일부/누락/미확인으로 분할한다. 각 목록은 서로 겹치지 않는다.

- confirmed: 방향의 모든 관계를 실제 시험하는 문항 대응이 있다.
- partial: 방향의 일부 관계만 실제 시험한다.
- missing: 실제 시험하는 관계가 없다고 검토했다. 제공/해설만 있는 경우도 여기에 해당할 수 있다.
- unknown: 자료나 검토가 부족하다. 코드가 missing으로 바꾸지 않는다.

covered는 최소 하나의 required 방향이 있고 모든 required가 confirmed이며 undecided가 없을 때만 가능하다. 선택 방향의 미완료는 그대로 남긴다. partial 판정에는 실제 확인된 부분과 미해결 부분이 모두 필요하다. gap은 검토된 부재이며 unknown과 다르다. excluded에는 `out_of_scope`/`duplicate`/`non_retrievable` 중 명시적 근거가 필요하며 target_ids는 비운다. 다른 판정의 exclusion_basis는 null이다. 낮은 중요도를 제외 사유로 쓰지 않는다.

같은 문항에서 같은 관계를 한 대응에서는 제공, 다른 대응에서는 시험으로 적으면 거절한다. '해설에만 등장'은 시험/제공과 겹치지 않는다. 하나의 질문이 실제로 여러 방향을 시험한다는 의미 주장은 별도 검토 대상이며, 이 묶음은 한 번의 학습 평가를 여러 방향에 자동 적용하지 않는다.

## 출력·실패·보존

성공하면 learning-links.json, manifest.json, validation.json, review.md, complete.json을 만든다. complete.json의 출력 해시로 묶음 일관성을 확인할 수 있다. 입력 전후 지문을 비교하고 기존 출력 덮어쓰기를 거절한다. 같은 입력/도구 판에서는 출력이 결정적이다.

입력 오류는 종료 코드 1, 인자 누락은 2다. 유효한 묶음의 gap/unknown은 구조 실패가 아니므로 종료 코드 0과 해당 판정으로 남긴다. 출력 도중 실패하면 가능한 한 failure.json과 부분 파일을 보존하며 complete.json은 없다. 실패 폴더를 완료 결과로 읽지 말고 원인을 해결한 뒤 **다른 새 출력 폴더**를 사용한다.

기존 프롬프트·출제/검수 상한·은행·학습·개인 수정·제외 기록과 별도다. [작성/검토 안내](mapping-review.md)를 기존 검수 경로에 자동 삽입하지 않는다.
