# Main-Quiz 앞 단계 'Different title' 보류 수정

## 문제와 사용자 효과
러너가 Main-Quiz 요청을 받아 앞 단계(Map·출제포인트 추출)를 돌리다 `Main-Quiz 앞 단계 보류: Different title`로 멈췄다
(runs/agent.261104_03.log, 2026-11-11 사용자 제보: 「작업 중지·실패 · Quiz Bank 를 못 만들었다」).
모델이 Map 또는 points JSON의 `title`을 요청 강의명과 한 글자라도 다르게 적으면(공백·괄호·줄임 등)
내용이 모두 맞아도 단계 전체가 보류됐다. `title`은 요청의 강의명을 되풀이하는 칸일 뿐 모델이 판단할 내용이 아니다.
게다가 이 검사 실패는 `state.json`에 failed로 남지 않고 started로 남아 원인이 폴더에 기록되지 않았다.

## 범위와 성공 기준
- Map·points·point-repair 결과의 `title`이 요청과 다르면 모델 원문을 `model-<파일>`로 보존하고 `title`만 요청값으로 맞춘다.
  state.json에 `modelTitle`로 모델이 적은 값을 남긴다. 나머지 검사(스키마·쪽·ID·트리)는 그대로다.
- 결과 검사 실패는 호출 실패처럼 failure.json·state failed로 남긴다(자동 재실행 없음은 그대로).
- 서버 계약(`map_tree.check_outputs`의 title 일치)은 바꾸지 않는다. 러너가 맞춘 title로 통과한다.
