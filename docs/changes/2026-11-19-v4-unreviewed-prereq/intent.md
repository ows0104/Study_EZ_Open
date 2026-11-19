# Main-Quiz /4 조립: 검토가 확인하지 않은 선행 연결을 투영에서 뺀다

## 문제와 사용자 효과
- 261109_02 job 700(운영자 제공 웹 normalize, docs/changes/2026-11-19-operator-normalize-import)이 GPT 단계 58개를 거절 없이 마쳤다.
  그런데 조립(`generation_v4._compile`)이 `roots: prerequisite needs a matching reviewed relation`으로 멈춰 게시되지 않는다.
- 웹 normalize에 목표 사이 선행 연결이 둘 있다(T026→T027 R0208, T070→T071 R0209). 지도 검토(v4-map-check-0)는 둘 다 `unknown`으로 판정했다.
  - 「선행 회상이 필수」라는 근거가 자료에 없다는 판정이다.
- 과제 순서(`assemble`)는 검토가 지지한 관계의 선행 연결만 쓴다. 그런데 그 앞의 `_compile` 투영은 연결을 그대로 두고, 「검토된 관계」를 요구하는 brief 검사를 부른다.
- 모델 normalize는 선행 연결을 거의 내지 않아 그동안 드러나지 않았다.

## 범위와 성공 기준
- `_compile`의 투영 brief에서, 지도 검토가 `supported`로 판정하지 않은 관계의 선행 연결을 뺀다. `assemble`과 같은 규칙이다.
- 지지된 연결은 그대로 남는다.
- job 700 사본(`C:\sez\rp\a700`)을 모델 호출 없이 다시 돌려 결과까지 간다. 서버 검사(validate_result)도 통과한다.
- 그 뒤 job 700을 이어 해서 게시한다.

## 근거·미정 사항
- 사용자 2026-11-19: 「고쳐서 이어 해」.
- /2·/3 계약은 건드리지 않는다(바이트 동일 보존 원칙).
