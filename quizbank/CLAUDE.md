# quizbank — Quiz Bank 정리·검증·검토

ChatGPT 가 만든 문제은행 응답(마크다운) 한 편 → 서버에 올릴 JSON · 외부지식 검토 · 인용 쪽 PNG.

    한 명령                 python -m quizbank.run <raw.md> --pdf <필기.pdf> --title … --run-id … --out …
    검사                    pytest tests/quizbank
    권한 · 어디서나 미는 함정  ../CLAUDE.md
    돌리는 쪽               ../runner/ (`runner bank`)

## 이 덩이가 하는 일과 안 하는 일

**만들지 않는다.** 문항은 ChatGPT 가 만든다 — 관리자가 사이트 캘린더 패널에서 「Quiz Bank 만들기」를
누르면 확장이 필기 PDF 와 족보 조각을 붙여 ChatGPT 를 연다. 생성 프롬프트의 정본은
`web/src/bank/bankPrompt.md` 다(2026-10-04부터 v1.1, 그 전은 AdaptiveStudy3).

    정리     organize.py   눈먼 claude -p 가 표·블록 응답을 스키마(schema.py)로 옮긴다. 고치지 않는다
    검증     validate.py   구조만 잰다. errors 가 있으면 학생에게 안 연다
    검토     review.py     다른 눈먼 세션이 정답을 자기 의학 지식으로 본다. 표시만 한다
    슬라이드  slides.py     문항이 인용한 필기 PDF 쪽(여러 장 가능)을 PNG 로

## 경계

러너가 **하위 프로세스로만** 부른다(`python -m quizbank.run`). 러너도 quizgen 도 import 하지 않고,
이 덩이도 그 둘을 import 하지 않는다 — `session.py` 가 quizgen/session.py 와 비슷한 30줄을 따로 둔 이유다.

## 이력

AdaptiveStudy3(형제 폴더, Node 로컬 시제품)의 `bank_builder/` 를 2026-10-04 에 옮겼다. 시제품에서
잰 것: 261002_02 에서 Claude 정리 176초(Codex 는 같은 응답에 10분 시한 초과), 외부지식 검토 36문항
36초 — 망가진 족보 정답표를 가르치던 두 장을 wrong 으로 잡았다.
