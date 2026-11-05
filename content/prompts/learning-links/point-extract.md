위 필기와 족보를 보고 출제포인트를 추출해줘. 학습자가 어떤 대상을 만났을 때 필요한 지식과 개념 사이의 연결을 스스로 떠올리고, 구별·설명·판단·적용할 수 있어야 하는지 구체적으로 정리해줘.

- 원본 전체의 본문·필기·교수 강조·표·그림을 살펴보고 실제 학습 목표와 회상할 대상을 구체적으로 찾아줘.
- 각 포인트는 하나의 의미 있는 회상·판단 목표로 정리해줘. 어떤 단서에서 무엇을 답해야 하는지, 필요한 관계·조건·예외와 답의 범위를 드러내줘. 함께 기억할 가치가 있는 분류·목록·비교·기전·과정은 묶고, 따로 회상할 가치가 있는 세부는 독립 목표로 보존해줘.
- 세부 지식으로 들어가는 중요한 기초 연결도 살펴봐. 개념→분류·역할, 구조→기능, 원인→결과, 현상→설명, 상황→사용할 개념, 조건→성립·예외 등에서 실제 필요한 연결을 찾아줘.
- 주어진 관계를 활용하는 목표와, 그 관계 자체를 스스로 떠올리는 목표를 구별해줘. 학습 가치에 따라 필요한 회상 방향과 답의 수준을 선정하고, 그림을 보고 식별·해석하는 목표와 글로 특징을 말하는 목표를 구별해줘.
- 족보에서 실제로 판단한 연결·조건·비교 기준과 선지의 혼동 지점을 읽어줘. 부정형 선지는 관계가 성립하거나 어긋나는 조건을 구별해줘. 기출 근거는 실제로 다룬 범위와 깊이에 맞춰 기록해줘.
- 중요성은 목표별 실제 근거로 설명해줘. 교수의 올해 출제 예고·강조, 학습목표, 해당 교수의 기출, 다른 교수의 참고 기출, 필기자 표시를 구별해줘. 강의 이해에 필요한 정도·시험 중요성·구체적인 임상 중요성은 각각 근거를 적고, 심화 여부도 별도로 판단해줘.
- 해당 강의·교수·연도의 자료와 포함·제외 범위를 지켜줘. 자료에 명시된 내용과 해석·불확실성을 구별하고, 중요도 근거가 부족하면 판단을 보류해줘. 원본에 없는 세부 지식으로 범위·난도를 늘리지 마.
- 관련 목표를 원본 흐름에 따라 묶고 독립적으로 회상할 가치가 있는 세부까지 확인해줘. 반복·부연은 해당 목표에 통합하고, 의미 있는 내용을 제외했다면 이유를 남겨줘.

## 출력 계약

최종 결과는 아래 구조의 JSON 객체 하나로 작성해줘. 모든 필드를 포함하고, 해당 항목이 없는 목록은 [], 확인되지 않은 선택 정보는 null로 표현해줘. 상태를 판단하기 어려운 내용은 지정된 불확실성 상태와 이유를 남겨줘. 실제 항목 수는 원본에 맞춰 정해줘.

- extraction_status는 extracted(제공된 범위의 자료를 확인해 추출), partial(일부 자료 확인에 제한), unreadable(내용 추출 불가)이야. partial/unreadable에는 scope.limitations에 확인 범위와 이유를 적고, unreadable의 내용 목록은 []로 남겨줘. 이 상태는 추출 범위에 대한 기록이야.
- schema_version은 예시의 버전을 그대로 사용하고 title에는 실제 강의명을 적어줘.
- sources에는 제공된 원본의 source_id·파일명(label)·종류(notes/exam/other)·교수·연도·물리 쪽수를 적어줘. 제공된 source_id는 그대로 사용하고, 없는 경우 원본별 S1, S2 순서로 부여해줘. 교수·연도·쪽수가 미확인이면 null이야.
- scope에는 포함 범위(included), 제외 범위(excluded), 읽기 어려운 자료·출처 충돌·해석의 한계(limitations)를 적어줘.
- evidence와 visual_refs는 {"source_id":"S1","pages":[1],"locator":"실제 위치 설명"} 형식의 목록이야. pages는 PDF 물리 쪽 번호이며, 페이지를 특정하기 어려우면 []와 확인 가능한 locator를 사용해줘. 페이지를 확인한 경우 locator는 null이어도 돼.
- ID는 같은 결과 안에서 고유하게 부여하고, 참조에는 해당 결과에 실제로 존재하는 ID를 사용해줘. 근거 목록에는 sources의 ID를 연결해줘. 제공된 원본 정보와 확인된 내용에 따라 작성하고, 불확실한 부분은 이유와 함께 보존해줘.

### 출제포인트 필드 작성

- summary에는 검토한 범위와 목표를 묶은 주요 판단을 적어줘.
- groups에는 관련 목표를 묶는 G1 순서의 group_id와 title을 적어줘. points의 각 항목은 실제 group_id에 연결해줘.
- points에는 P1 순서의 point_id, group_id, 실제 회상·판단 목표(objective)를 적어줘. requirement는 required(반드시 다룰 근거가 확인됨), optional(선택적 확장), undecided(판단 보류)이며 requirement_reason에 이유를 적어줘. 모든 group에 실제 포인트를 연결해줘.
- directions에는 목표의 필요한 회상 방향을 D1 순서의 direction_id로 적어줘. direction_id는 전체 결과에서 고유해야 해. cue는 무엇을 보고 떠올릴지, answer_scope는 어떤 범위까지 답할지, answer_elements는 그 범위를 충족하는 핵심 답 요소, relation은 실제 회상할 연결이야. 조건과 예외는 각각 conditions·exceptions에 적어줘. 이 항목들은 목표의 명세이며 완성 문항·선지·해설을 작성하는 단계는 별도야.
- visual_requirement는 required(그림을 보고 식별·해석해야 함), not_required(그림 없이 회상 가능), uncertain(판단 보류)이야. 필요한 실제 시각 자료의 위치를 visual_refs에 적고, 자료를 특정하기 어려우면 scope.limitations에 이유를 남겨줘. 모든 방향에는 실제 원본 evidence를 적어줘.
- importance는 structural(강의 이해), exam(시험), clinical(구체적인 임상 판단)의 근거를 각각 적는 객체야. 각 status는 supported(근거 확인), uncertain(판단 보류), not_identified(근거를 찾지 못함) 중 하나이며 reason·basis·evidence를 적어줘. not_identified는 중요도 0이나 출제 가능성 0이라는 의미가 아니야.
- structural.basis는 structural_rationale, clinical.basis는 clinical_rationale를 사용해줘. exam.basis는 learning_objective, professor_exam_hint, professor_emphasis, same_professor_exam, other_professor_exam, note_taker_emphasis 중 실제 근거를 골라줘. supported에는 근거 종류와 실제 출처를 함께 기록해줘. 교수·연도·족보 번호·직접/간접 발언 등 구체적인 근거는 reason과 evidence.locator에 보존해줘. 같은 교수인지 미확인이면 uncertain으로 남겨줘.
- advanced는 중요도와 별개인 추가 추론·연계 여부야. status는 yes/no/uncertain이며 reason에 해당 목표의 판단 이유를 적어줘.
- excluded_candidates에는 검토 후 제외한 의미 있는 후보의 description·reason·evidence를 남겨줘.
- Map을 입력으로 요구하지 않는 독립 결과야. 목표·방향의 ID는 이 결과 안에서 부여하고, 같은 개념을 다룬다는 사실과 Map과의 실제 대응은 이후 연결 단계에서 판단해줘.

### 형식 예시

아래는 구조를 보여주는 합성 예시야. 실제 목표·방향·답 요소 수와 내용은 강의에 맞춰 작성해줘.

```json
{
  "schema_version": "exam-point-extract/1",
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
  "summary": "정의에 근거한 포함 관계를 회상 목표로 정리한다.",
  "groups": [
    {
      "group_id": "G1",
      "title": "사각형의 포함 관계"
    }
  ],
  "points": [
    {
      "point_id": "P1",
      "group_id": "G1",
      "objective": "정사각형을 직사각형의 하위 분류로 연결한다.",
      "requirement": "required",
      "requirement_reason": "포함 관계가 합성 자료의 명시적 학습목표다.",
      "directions": [
        {
          "direction_id": "D1",
          "cue": "정사각형의 상위 분류는?",
          "answer_scope": "네 각이 직각이라는 정의에 따른 상위 분류.",
          "answer_elements": [
            "직사각형"
          ],
          "relation": "정사각형 → 직사각형의 한 종류",
          "conditions": [],
          "exceptions": [],
          "visual_requirement": "not_required",
          "visual_refs": [],
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
      "importance": {
        "structural": {
          "status": "supported",
          "reason": "사각형 분류를 이해하는 기초 연결이다.",
          "basis": [
            "structural_rationale"
          ],
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
        "exam": {
          "status": "supported",
          "reason": "합성 자료의 학습목표에 명시되어 있다.",
          "basis": [
            "learning_objective"
          ],
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
        "clinical": {
          "status": "not_identified",
          "reason": "이 합성 자료에서 임상 근거는 확인되지 않는다.",
          "basis": [],
          "evidence": []
        }
      },
      "advanced": {
        "status": "no",
        "reason": "명시된 분류의 직접 회상이다."
      }
    }
  ],
  "excluded_candidates": [],
  "extraction_status": "extracted"
}
```
