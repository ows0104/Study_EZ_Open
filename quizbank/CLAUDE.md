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

## 걸린 문항만 빼고 연다 (2026-10-05)

**관리자 지시** — 261002_03 이 56문항 중 2문항 때문에 통째로 막히자 「걸린 문항만 빼고 연다」.
`validate.validate_dropping` 이 문항 ID 로 시작하는 오류(`Q046: …`)만 그 문항 탓으로 보고 빼고 다시 잰다.

    뺀 문항       validation.dropped — 문항 원문과 이유. 관리자 패널에 「검증에 걸려 뺀 문항 N개」
    빼기 전 은행   bank.raw.json (러너 산출물에만. 서버에는 뺀 은행이 간다)
    선행 정리      뺀 문항을 선행으로 든 문항은 그 선행만 지운다. 그래서 기초를 잃은 통합 문항은 다음 회차에 같이 빠진다
    통째로 막기    문항 하나의 탓이 아닌 오류(개념·계획·출처 요약·구조)가 하나라도 있으면 지금처럼

## 충돌은 합치고 외부 의학지식으로 정한다 (프롬프트 v1.2, 2026-10-05)

**관리자 지시** — 「외부 의학지식을 충분히 이용해도 되는데, 자료에 없거나 다른 경우에 표시만 해 주면 돼.
충돌이 있는 문제들은 합치고 표시만 해줘.」 v1.1 은 충돌을 출처별 문항으로 갈랐는데, 261002_03 에서 족보 쪽
문항(Q009)이 틀린 답을 그대로 가르쳤다(외부지식 검토가 wrong).

    합친 충돌 문항    conflict_id + 충돌 기록의 description(각 출처의 말 · 고른 정답 · 근거). 학생은 답 아래서 읽는다
    자료 밖 내용      source_refs 의 `EXT` · source_strength `external_knowledge`. 학생 화면에 한 줄 표시
    검증              「[출처 기준] 머리말」·「출처 하나로 분리」를 걷었다. 갈라 낸 옛 판 문항도 그대로 통과한다

## 경계

러너가 **하위 프로세스로만** 부른다(`python -m quizbank.run`). 러너도 quizgen 도 import 하지 않고,
이 덩이도 그 둘을 import 하지 않는다 — `session.py` 가 quizgen/session.py 와 비슷한 30줄을 따로 둔 이유다.

## 이력

AdaptiveStudy3(형제 폴더, Node 로컬 시제품)의 `bank_builder/` 를 2026-10-04 에 옮겼다. 시제품에서
잰 것: 261002_02 에서 Claude 정리 176초(Codex 는 같은 응답에 10분 시한 초과), 외부지식 검토 36문항
36초 — 망가진 족보 정답표를 가르치던 두 장을 wrong 으로 잡았다.
