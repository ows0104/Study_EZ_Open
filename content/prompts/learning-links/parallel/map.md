위 필기와 족보를 보고, 강의의 큰 구조에서 세부 개념으로 이어지는 Concept map을 만들어줘.

- 실제 학습 목표에 따라 개념을 묶고, 분류·순서·목적 등 강의의 큰 흐름을 드러내줘.
- 각 개념이 어디에 속하고 왜 연결되는지, 비슷한 개념은 어떻게 다른지 표현해줘. 관계의 의미와 중요한 방향·조건이 드러나게 적어줘.
- Tree-like한 큰 구조에 여러 맥락과 가지 사이의 교차 연결을 유연하게 표현해줘. 연결은 자료에서 확인되는 의미를 바탕으로 선정해줘.
- 필기 전체와 족보를 함께 살펴보고, 해당 강의의 범위와 자료에 근거해 구성해줘. 중요한 불확실성이나 자료의 한계는 notes에 남겨줘.

## 출력

전체 결과를 실제 UTF-8 JSON 파일 concept-map.json으로 작성하고 다운로드 링크를 제공해줘. 파일 안에는 아래 구조의 JSON 객체 하나를 담아줘.

- schema_version은 concept-map-extract/2, title은 강의명이야. overview에는 강의의 큰 흐름을 짧게 적어줘.
- concepts의 concept_id는 C001부터 부여하고, title은 짧은 개념명, core_facts는 의미를 이해할 핵심 내용 목록으로 적어줘.
- relations의 from_id와 to_id는 연결되는 두 개념 ID야. relation에 두 개념의 관계를 짧은 문장으로 설명해줘. 같은 개념이 여러 개념과 연결될 수 있어.
- source_refs에는 제공된 원본 ID와 실제 근거 위치를 남겨줘. pages는 PDF 물리 쪽 번호이며, 페이지를 특정하기 어려우면 []와 확인 가능한 locator를 써줘. 위치 설명이 따로 필요 없으면 locator는 null이야.
- notes에는 자료 충돌·불확실한 해석·확인하지 못한 범위를 간단히 적어줘. 해당 사항이 없으면 []야. 자료를 읽을 수 없어 내용을 추출하지 못했다면 내용 목록은 []로 두고 그 이유를 notes에 적어줘.

아래는 S1의 1쪽에 사각형 정의와 포함 관계가 제시된 합성 예시야. 개념과 관계의 수·내용은 실제 강의에 맞춰 작성해줘.

```json
{
  "schema_version": "concept-map-extract/2",
  "title": "사각형 분류",
  "overview": "정의와 포함 관계로 사각형의 큰 분류를 이해한다.",
  "concepts": [{"concept_id": "C001", "title": "정사각형", "core_facts": ["네 각이 직각이고 네 변의 길이가 같은 사각형."], "source_refs": [{"source_id": "S1", "pages": [1], "locator": null}]}, {"concept_id": "C002", "title": "직사각형", "core_facts": ["네 각이 직각인 사각형."], "source_refs": [{"source_id": "S1", "pages": [1], "locator": null}]}],
  "relations": [{"from_id": "C001", "to_id": "C002", "relation": "정사각형은 직사각형의 한 종류다.", "source_refs": [{"source_id": "S1", "pages": [1], "locator": null}]}],
  "notes": []
}
```
