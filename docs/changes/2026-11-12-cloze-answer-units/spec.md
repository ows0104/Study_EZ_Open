# Main-Quiz cloze 정답 단위를 발문 빈칸에 맞춤 — 설계

## 요구사항과 수용 기준
- R1 서버 `root_learning.content.answer`: `format == 'cloze'`이고 저장된 단위가 있으면 `answerUnits`는
  `normalize_cloze(q)['answer_units']`(발문 `{빈칸}` 순서)다. 인라인 빈칸이 없는 발문은 저장값 그대로.
  단위가 빈 문항(정답을 고친 개인 수정본)은 빈 채로 둔다.
- R2 계약 `generation_v3.cloze_units(bank)`: 같은 규칙으로 bank의 cloze 단위를 제자리에서 맞추고 바뀐 것
  `{question_id, from, to}`을 돌려준다. 두 번 불러도 같다.
- R3 생성기에서 모델이 쓴 문항이 은행에 들어오는 곳 세 군데에 적용: `merge_added`, `merge_fixes`
  (계약, v3·v4 생성기가 모두 부른다), `connection_generate_v3/v4._intake`(접수 직후).
  접수에서 바뀐 것은 결과 manifest의 `intakeClozeUnits`에 남는다(없으면 키 없음).

## 책임·입출력 계약·오류 상태
- 오류를 새로 내지 않는다. 맞추기만 한다(막으면 야간 일괄 출제가 서는데, 화면에서 바로잡을 수 있는 차이다).
- `intake_projection`은 바꾸지 않는다. 서버 `check_result`가 패킷에서 다시 계산해 manifest와 정확히 비교하므로,
  바꾸면 러너·서버 버전이 엇갈리는 동안 결과가 거절된다. `initialBank`·`merge_*`는 서버가 다시 만들지 않는다.
- `generation_v4.check_coverage`의 단위 수(저장값)는 그대로 둔다. 맞춘 뒤에는 저장값 = 빈칸 수이고,
  옛 결과를 다시 검사할 때 판정이 바뀌지 않게 한다.

## 호환성과 데이터 보존
- DB·게시된 판·학습 기록·개인 수정 불변. 응답 모양(`answerUnits` 배열) 불변.
- manifest에 선택 키 하나 추가(`MANIFEST_KEYS`는 부분집합 검사라 옛 서버도 받는다).
- 새 러너로 옛 실행을 이어 하면, 접수 은행에 어긋난 cloze가 있던 실행은 뒤 단계 입력 지문이 달라져
  「달라진 호출은 자동 재실행하지 않습니다」로 멈춘다. 이어 하기(`--resume`)가 필요하다.
