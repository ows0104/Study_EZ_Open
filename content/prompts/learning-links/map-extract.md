위 필기와 족보를 보고, 강의의 큰 구조에서 세부 개념으로 이어지는 Concept map을 만들어줘. 강의 전체가 무엇을 설명하는지, 각 개념이 어디에 속하고 서로 어떻게 연결되는지 이해할 수 있게 구성해줘.

- 강의의 중심 질문·목적과 실제 학습 목표를 파악하고, 분류·순서·목적 등 큰 흐름에 따라 개념을 묶어줘. 내용의 성격과 깊이에 맞게 큰 구조와 세부를 구성해줘.
- Tree-like한 큰 구조에 여러 맥락과 가지 사이의 교차 연결을 함께 표현해줘. 관계는 원본에서 확인되는 의미를 바탕으로 선정해줘.
- 상하위 분류, 원인과 결과, 과정의 순서, 구조와 기능, 비교, 적용 조건을 구별해줘. 방향·성립 조건·예외가 중요한 연결에는 이를 함께 표시해줘.
- 비슷한 개념의 공통점과 구별 기준을 드러내고, 함께 이해할 내용은 묶어줘. 서로 다른 분류 기준과 독립적인 세부는 알아볼 수 있게 표현해줘.
- 필기 전체의 본문·필기·표·그림에서 강의 구조를 파악하고, 족보에서 다룬 개념과 관계·혼동 지점을 함께 살펴봐.
- 해당 강의·교수·연도의 자료와 포함·제외 범위를 기준으로 구성해줘. 자료 간 충돌과 불확실한 해석은 확인된 관계와 구별해줘.

## 출력 계약

최종 결과는 아래 구조의 JSON 객체 하나로 작성해줘. 모든 필드를 포함하고, 해당 항목이 없는 목록은 [], 확인되지 않은 선택 정보는 null로 표현해줘. 상태를 판단하기 어려운 내용은 지정된 불확실성 상태와 이유를 남겨줘. 실제 항목 수는 원본에 맞춰 정해줘.

- extraction_status는 extracted(제공된 범위의 자료를 확인해 추출), partial(일부 자료 확인에 제한), unreadable(내용 추출 불가)이야. partial/unreadable에는 scope.limitations에 확인 범위와 이유를 적고, unreadable의 내용 목록은 []로 남겨줘. 이 상태는 추출 범위에 대한 기록이야.
- schema_version은 예시의 버전을 그대로 사용하고 title에는 실제 강의명을 적어줘.
- sources에는 제공된 원본의 source_id·파일명(label)·종류(notes/exam/other)·교수·연도·물리 쪽수를 적어줘. 제공된 source_id는 그대로 사용하고, 없는 경우 원본별 S1, S2 순서로 부여해줘. 교수·연도·쪽수가 미확인이면 null이야.
- scope에는 포함 범위(included), 제외 범위(excluded), 읽기 어려운 자료·출처 충돌·해석의 한계(limitations)를 적어줘.
- evidence는 {"source_id":"S1","pages":[1],"locator":"실제 위치 설명"} 형식의 목록이야. pages는 PDF 물리 쪽 번호이며, 페이지를 특정하기 어려우면 []와 확인 가능한 locator를 사용해줘. 페이지를 확인한 경우 locator는 null이어도 돼.
- ID는 같은 결과 안에서 고유하게 부여하고, 참조에는 해당 결과에 실제로 존재하는 ID를 사용해줘. 근거 목록에는 sources의 ID를 연결해줘. 제공된 원본 정보와 확인된 내용에 따라 작성하고, 불확실한 부분은 이유와 함께 보존해줘.

### Map 필드 작성

- central_question과 overview에는 강의의 중심 질문과 큰 흐름을 적어줘.
- sections는 읽기 위한 주요 묶음이야. G1 순서로 section_id를 부여하고 title·summary·concept_ids를 적어줘. 같은 개념이 여러 묶음에 속할 수 있어.
- concepts에는 C1 순서의 concept_id, 개념명(label), 의미를 구별할 짧은 description, 실제 evidence를 적어줘. 모든 개념을 하나 이상의 section에 포함해줘.
- relations에는 R1 순서의 relation_id와 실제 두 개념의 from_id·to_id, 관계 종류(kind), 방향(direction), 관계의 의미를 설명하는 label, 성립 조건(condition), 예외(exceptions), support, evidence를 적어줘. 조건이 따로 없으면 condition은 null이야.
- kind는 is_a(하위 종류→상위 분류), part_of(부분→전체), causal(원인→결과), sequence(이전→이후), structure_function(구조→기능), comparison(비교 대상 간), application(개념→활용 대상), association(그 밖의 의미 있는 연관) 중에서 선정해줘. 서로 다른 관계를 가진 같은 개념 쌍도 표현할 수 있어.
- direction은 directed 또는 undirected야. 비교는 undirected, 분류·부분·인과·과정·구조와 기능·활용은 위에서 정한 방향의 directed로 적어줘. association은 내용에 맞는 방향을 선택해줘. 분류·부분 관계는 포함 구조가 일관되게 이어지도록 구성하고, 다른 관계는 실제 순환이나 교차 연결도 표현해줘.
- support.status는 direct(원본에 명시), inferred(원본을 근거로 해석), uncertain(관계를 확정하기 어려움)이야. reason에는 판단 이유를 적어줘. direct/inferred에는 실제 evidence를 남기고, uncertain은 확인된 근거와 부족한 점을 기록해줘.

### 형식 예시

아래는 구조를 보여주는 합성 예시야. 개념·관계·묶음의 수와 내용은 실제 강의에 맞춰 작성해줘.

```json
{
  "schema_version": "concept-map-extract/1",
  "title": "사각형 분류",
  "sources": [
    {
      "source_id": "S1",
      "label": "합성 예시 자료: 사각형 분류",
      "kind": "notes",
      "professor": null,
      "year": null,
      "page_count": 1
    }
  ],
  "scope": {
    "included": [
      "사각형의 정의와 분류"
    ],
    "excluded": [],
    "limitations": [
      "출력 형식을 설명하는 비의학 합성 예시다."
    ]
  },
  "central_question": "정사각형과 직사각형은 어떤 분류 관계인가?",
  "overview": "도형의 정의를 기준으로 포함 관계를 구성한다.",
  "sections": [
    {
      "section_id": "G1",
      "title": "정의와 포함 관계",
      "summary": "정의의 조건으로 두 도형을 연결한다.",
      "concept_ids": [
        "C1",
        "C2"
      ]
    }
  ],
  "concepts": [
    {
      "concept_id": "C1",
      "label": "정사각형",
      "description": "네 각이 직각이고 네 변의 길이가 같은 사각형.",
      "evidence": [
        {
          "source_id": "S1",
          "pages": [
            1
          ],
          "locator": "사각형 분류"
        }
      ]
    },
    {
      "concept_id": "C2",
      "label": "직사각형",
      "description": "네 각이 직각인 사각형.",
      "evidence": [
        {
          "source_id": "S1",
          "pages": [
            1
          ],
          "locator": "사각형 분류"
        }
      ]
    }
  ],
  "relations": [
    {
      "relation_id": "R1",
      "from_id": "C1",
      "to_id": "C2",
      "kind": "is_a",
      "direction": "directed",
      "label": "정사각형은 직사각형의 한 종류다.",
      "condition": null,
      "exceptions": [],
      "support": {
        "status": "direct",
        "reason": "합성 자료가 두 정의와 포함 관계를 명시한다."
      },
      "evidence": [
        {
          "source_id": "S1",
          "pages": [
            1
          ],
          "locator": "사각형 분류"
        }
      ]
    }
  ],
  "extraction_status": "extracted"
}
```
