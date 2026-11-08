# Measure recall load and structural answer cues in the bank checker

## 문제와 사용자 효과
관리자가 2026-11-08 Main-Quiz 문항 퀄리티를 지적했다 — 「초등학생이 문장 구조만 봐도
X라고 하겠다」, 「답이 너무 길면 회상이 힘들다. 그 정도로 길면 cloze나 객관식으로 내던가」.

진단(같은 날, 운영 DB 읽기 전용 조회): 감염과 면역 `261104_02`
revision `main-quiz-reviewed-6143c8c89ad64d9c` 98문항에서
- 예/아니오로 답하는 문항 6개(Q003·Q004·Q079·Q080·Q107·Q109)의 **정답이 전부 부정**이고
  발문 단서도 반드시·~라는 이유만으로 한 방향뿐이다 — 지식 없이 맞는다.
- basic/list 정답이 60자를 넘는 것이 21개(22%), 채점 단위가 30자를 넘는 것이 16.4%.
- **cloze 0개 · 객관식 0개** — 긴 정답을 돌릴 형식을 한 번도 쓰지 않았다.

정본 프롬프트에는 규칙이 있다(§2.1 질문 축 보존, §3.4 최소 채점 단위, §3.5 형식·단정어).
`quizbank/generate.py:item_quality_guidance()` 가 그 절들을 CLI 저작·repair 단계에 붙이므로
규칙은 전달된다. **측정이 없다** — 기존 품질 검사는 `leaked_units()`(발문에 정답 문자열이
그대로 들어갔는가) 하나뿐이라 위 세 가지는 아무도 세지 않았다.

측정이 붙으면 repair 단계 입력(`validation`)과 관리자 화면 issues 로 돌아가, 다음 판에서
작성자가 같은 자리를 고칠 수 있다.

## 범위와 성공 기준
`studyez_contracts/bank/quality.py` 에 측정 다섯 개를 더하고 검사를 새로 쓴다. 전부
**warnings** 다 — `validate_dropping` 은 errors 만 보고 문항을 빼므로, 측정이 문항을
떨어뜨리거나 게시를 막지 않는다. 성공 기준:

- 2026-11-07 Main-Quiz 한 편에서 다섯 측정이 모두 걸리고 Q003·Q080 이 이름으로 나온다.
- 운영 Quiz Bank 35편(3,103문항)에서 새 경고가 편당 중앙 2개 수준이고 errors 는 늘지 않는다.
- 옛 3.0 은행은 아무 변화가 없다.

프롬프트·DB·서버 경로·웹 화면·운영 데이터는 바꾸지 않는다.

## 근거·미정 사항
사용자 승인(2026-11-08, 현재 채팅): 진단 네 후보 중 「검사기에 측정 추가」. 이 발언을
이 파일·검사·작업 기록 변경의 승인으로 적용하고, 프롬프트 수정·재출제·배포로 넓히지 않는다.

대시보드 겹침 확인·등록 push 완료(`dashboard` b5a708ce). 가장 가까운 작업은
`claude/infection-path1-map` 의 `studyez_contracts/roots`·`learning_links` 검증이며
이 작업은 `studyez_contracts/bank` 만 건드린다.

미정: 선(선 숫자)은 운영 Quiz Bank 의 분포 p97 에서 잡았을 뿐 교육적 근거로 고른 값이 아니다.
관리자가 더 조이자고 하면 숫자만 바꾼다. 웹 Quiz Bank 관리자 목록은 `errorCount` 만 내보내
새 경고가 목록에 숫자로 보이지 않는다 — 별도 작업이다.
