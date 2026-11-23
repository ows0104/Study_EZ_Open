# Main-Quiz /4 정규화: 포인트를 강의 뼈대로 묶어 목표를 짠다

## 문제와 사용자 효과

레오·코로나·노로바이러스(조남혁, 261118_05, job 704, generation `d51b2e83…`)에서 같은 normalize 입력을
CLI(Codex)와 ChatGPT Work가 각각 정규화했다(2026-11-18). 뒤 단계는 같은 코드로 끝까지 돌렸고 Work판을 게시했다
(`runs/_development/2026-11-19-261118_05-work-normalize/README.md`).

| | CLI normalize | Work normalize |
|---|---|---|
| 목표 역할 | leaf 100 · branch 18 · root 0 | root 9 · branch 81 · leaf 41 |
| 목표 만드는 법 | 포인트 하나 → 목표 하나(T079 = P079, 제목 = 포인트 질문) | 주제로 묶음(root 「세 바이러스의 과 분류」 → leaf 「코로나의 목–과 분류」) |
| 지도 밖 개념 | 222개, 답 조각마다(`F002_1_3` 「Rotavirus–Reoviridae」) | 101개, 비교 묶음 단위 |
| 관계 종류 | 271개 전부 association | association 182 · 비교 9 · 인과 7 · 순서 2 · 선행 2 |

뒤 단계 결과에서 Work판은 바이러스·단계를 잇는 문항이 더 많았고, 모든 포인트에 문항이 있었고,
족보 포인트당 문항이 4.47개(CLI 3.11)였다.

**두 쪽이 받은 지시문은 같았다.** 차이는 끝의 전달 방식(CLI 파일·영수증 / 웹 첨부·다운로드)뿐이다
(`generation.cli-normalize/.native/normalize/work/task.md`와 `Downloads/261118_05_웹입력/프롬프트.txt` 비교).
CLI는 포인트마다 한 줄씩 직접 쓴 `DATA`를 `build.py`로 목표 하나씩 찍었다. 내용 판단은 모델이 했지만
목표 구조는 포인트 목록을 그대로 따랐다. 지시문에는 목표를 묶으라는 말이 없고, 오히려
「그 관계를 이미 포인트에서 온 방향이 회상시키면 같은 내용의 관계 방향을 따로 만들지 않는다」가 있어
CLI는 갈래를 넘는 목표를 거의 만들지 않았다(build.py `covered` 표). Work는 같은 지시문에서 스스로 묶었다.

사용자 2026-11-23: 「CLI normalize도 Work처럼 묶게 고쳐줘.」

## 범위와 성공 기준

- root-generation/4의 normalize 지시문(`content/prompts/learning-links/v4/normalize.md`)만 바꾼다.
  출력 스키마·수용 검사·누락 점검·뒤 단계 지시문·코드는 그대로다.
- 성공 기준: 261118_05의 저장된 normalize 입력(`normalize.input.json`, 입력 지문 f8b43e…)으로 새 지시문을 재생했을 때
  - root·branch 목표가 생기고(포인트 1:1이 아님), 포인트가 여러 목표에 붙거나 여러 포인트가 한 목표로 묶이며,
  - 원본이 말하는 비교·인과·순서 관계가 association 밖의 kind로 나오고,
  - 답 조각마다 개념을 만드는 일이 줄며,
  - 11-11에 막은 것(이름만 끼운 관계 cue, 문장 통째 component)이 되살아나지 않는다.
  수치 목표는 정하지 않는다. 재생 결과를 release.md에 기록한다.

## 근거·미정 사항

- 재생 한 번은 표본 하나다. CLI·Work의 모델과 자료 보기(CLI는 쪽 축소 모음을 직접 만들어 봄, Work는 PDF)도 달랐다.
  지시문이 바꿀 수 있는 것은 목표 구조뿐이다.
- 뒤 단계 효과(연결 문항·포인트 밀도·cloze 표 모양·의학 위험)는 normalize 재생으로 확인되지 않는다.
  끝까지 돌리는 비교(약 80분, Codex 사용량)는 이번 범위 밖이며 사용자가 따로 정한다.
- Work판의 약점(커버리지 unknown 15, 둘 중 고르기 문항의 답 노출)은 뒤 단계에서 생겼고 이번 범위가 아니다.
- 과목 하나의 모양을 지시문에 박지 않는다. 예시는 실제 강의가 아닌 일반 예로 쓴다.
