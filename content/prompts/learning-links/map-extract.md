위 필기와 족보를 보고, 강의의 큰 구조에서 세부 개념으로 이어지는 Concept map을 만들어줘.

- 강의 전체의 중심 주제에서 주요 갈래와 세부 개념으로 이어지는 큰 흐름을 구성해줘. 실제 학습 목표에 맞춰 분류·기전·효과·활용 등 해당 강의에 자연스러운 묶음을 선정해줘.
- 각 노드는 짧은 개념명과 의미를 이해할 핵심 내용으로 표현해줘. 큰 갈래를 잡는 개요 노드와 구체적인 개념을 함께 두고, 주요 차이·작용·용도 등 필요한 내용은 짧게 묶어줘.
- 개념이 어디에 속하는지는 parent_id로, 왜 연결되는지는 relations로 드러나게 해줘. 큰 줄기의 분류와 가지 사이의 기전적·기능적 연결을 함께 표현하고, 서로 다른 분류 축과 비슷한 개념의 구별도 살려줘. 여러 개념이 하나의 개념으로 합쳐지는 연결도 표현할 수 있어.
- 필기 전체와 족보를 함께 살펴보고, 해당 강의의 범위와 자료에 근거해 구성해줘. 중요한 불확실성이나 자료의 한계는 notes에 남겨줘.
- 강의 전체를 몇 개의 큰 갈래로 나누고(최상위 개념 1~8개), 각 갈래 아래에 세부 개념이 2단계 이상 이어지도록 계층을 잡아줘. 엄격한 분류 트리가 아니어도 되며, 한 개념을 가장 자연스러운 한 갈래 아래에 두고 다른 갈래와의 관계는 relations로 이어줘.

## 출력

전체 결과를 실제 UTF-8 JSON 파일 concept-map.json으로 작성하고 다운로드 링크를 제공해줘. 파일 안에는 아래 구조의 JSON 객체 하나를 담아줘.

- schema_version은 concept-map-extract/3, title은 강의명이야. overview에는 강의의 큰 흐름을 짧게 적어줘.
- concepts의 concept_id는 C001부터 부여하고, parent_id는 이 개념이 속한 상위 개념 ID야(최상위 갈래는 null). title은 지도에 표시할 짧은 개념명, core_facts는 노드 안에 함께 표시할 간결한 핵심 내용 목록으로 적어줘.
- relations의 from_id와 to_id는 연결되는 두 개념 ID야. relation에 두 개념이 어떻게 연결되는지와 중요한 방향·조건을 짧게 설명해줘. 같은 개념이 여러 개념과 연결될 수 있어. parent_id로 이미 표현한 소속은 relations에 반복하지 않아도 되고, 갈래를 넘는 연결과 같은 갈래 안의 기전·비교·순서 연결을 적어줘.
- source_refs에는 제공된 원본 ID와 실제 근거 위치를 남겨줘. pages는 PDF 물리 쪽 번호이며, 페이지를 특정하기 어려우면 []와 확인 가능한 locator를 써줘. 위치 설명이 따로 필요 없으면 locator는 null이야.
- notes에는 자료 충돌·불확실한 해석·확인하지 못한 범위를 간단히 적어줘. 해당 사항이 없으면 []야. 자료를 읽을 수 없어 내용을 추출하지 못했다면 내용 목록은 []로 두고 그 이유를 notes에 적어줘.

아래는 S1의 1쪽에 사각형 정의와 포함 관계가 제시된 합성 예시야. 개념과 관계의 수·내용은 실제 강의에 맞춰 작성해줘.

```json
{"schema_version": "concept-map-extract/3", "title": "사각형 분류", "overview": "정의와 포함 관계로 사각형의 큰 분류를 이해한다.", "concepts": [{"concept_id": "C001", "parent_id": null, "title": "사각형", "core_facts": ["네 변으로 둘러싸인 도형."], "source_refs": [{"source_id": "S1", "pages": [1], "locator": null}]}, {"concept_id": "C002", "parent_id": "C001", "title": "직사각형", "core_facts": ["네 각이 직각인 사각형."], "source_refs": [{"source_id": "S1", "pages": [1], "locator": null}]}, {"concept_id": "C003", "parent_id": "C002", "title": "정사각형", "core_facts": ["네 각이 직각이고 네 변의 길이가 같은 사각형."], "source_refs": [{"source_id": "S1", "pages": [1], "locator": null}]}], "relations": [{"from_id": "C003", "to_id": "C002", "relation": "정사각형은 변의 길이 조건이 더해진 직사각형의 한 종류다.", "source_refs": [{"source_id": "S1", "pages": [1], "locator": null}]}], "notes": []}
```
