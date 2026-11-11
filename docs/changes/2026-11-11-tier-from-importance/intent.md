# Main-Quiz 추가·수정 단계: importance만 묻고 tier는 코드로, 품질 권고는 첫 수정에만

## 문제와 사용자 효과
아데노·폭스바이러스(방예지) root-generation/4 실행 `runs/_root-generation/6e5c581a8a334974b47cba85718e7ef5`
(2026-11-11, 96분)의 검토·수정 루프에서 206문항 중 123문항이 수정됐다. 그중 54문항은 모델 검토가 ok였고
코드 지적만으로 수정에 들어갔다.

- 52문항: 「중요도 수치는 Essential=5, Core=4, Important=3, Optional=2여야 합니다」. 모델이 tier와 importance를
  둘 다 써서 어긋났다. bank 3.3에서 둘은 일대일이고(`studyez_contracts/bank/priorities.py`), /3·/4는 조립 때
  포인트·문항 근거로 둘 다 다시 계산해 덮는다. 버려질 값을 고치려고 모델 수정이 돌았다.
- 43문항: 「회상 부담이 크다 — cloze·객관식으로 나눌지 검토」 같은 품질 권고(`bank/quality.py` warnings).
  권고라서 모델이 그대로 두면(예: Q014 1차 수정 무변경) 다음 라운드에 같은 경고로 다시 수정에 들어갔다.

## 범위와 성공 기준
- 추가·수정 단계 출력 스키마에서 문항·개념의 tier를 뺀다. importance는 2~5만 받는다.
- 합칠 때(`merge_added`·`merge_fixes`) tier를 importance로 채운다. 이전 실행의 캐시 출력에 tier가 있으면 버리고
  importance를 따른다.
- 품질 권고는 문항의 첫 수정에만 보낸다. 수정을 한 번 받은 문항은 권고만으로 다시 수정에 보내지 않는다.
  형식 오류(validate_bank errors)·검수 이력 표현은 그대로 보낸다.
- 성공 기준: 새 검사 통과, quizbank·contracts·runner 회귀 통과.

## 근거·미정 사항
- 사용자 승인(2026-11-11 채팅): 「기계적인 표시값 불일치 문제 해결해줘. 이런데 모델을 쓸 필요는 없을듯?」 →
  계획 제시 → 「지금 계획 좋아. 승인할게. 스키마 빼기도 하자. 근데 숫자가 편하니까 importance로 하자.
  검토 권고는 지시로 바꾸던가. 한번 안 바뀐건 넘기던가 해야할듯?」. 권고는 「한 번만 보내고 넘김」으로 진행.
- 처음 은행(1c, intake)은 이번 범위가 아니다. 들일 때 importance를 tier로 채우는 기존 방향(`intake_projection`)을 유지한다.
- 실제 모델 재생은 하지 않았다.
