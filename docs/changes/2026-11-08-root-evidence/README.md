# Main-Quiz 근거를 Quiz Bank 수준으로

## Intent
2026-11-08 사용자: 「Quiz bank와 마찬가지로 족보가 붙어야지」 → 차이 목록 보고 뒤
「1,2,3,5은 진행하고 6,7,8은 잘 통합가능할듯」.

| # | 항목 | 이번 범위 |
|---|---|---|
| 1 | 족보 슬라이드(연도·번호 표시) | 진행 |
| 2 | 족보 핵심 지면(족보만 근거인 문항은 맨 위) | 진행 |
| 3 | 핵심 근거 슬라이드 선택(나머지는 「추가 참고 슬라이드」로 접기) | 진행 |
| 4 | 다른 강의 슬라이드 | 제외(사용자가 고르지 않음) |
| 5 | 근거 상태 안내 | 진행 |
| 6 | 외부지식 검토 | 기존 「독립 정답 검수」 기록이 같은 역할 — 그대로 둔다 |
| 7 | 자료 충돌 설명 | 기존 「이 문항 검토 기록」 안에 통합 |
| 8 | 자료 밖(EXT) 표시 | 기존 「이 문항 검토 기록」 안에 통합 |

6·7·8의 「통합」은 따로 칸을 만들지 않고 이미 있는 검토 기록 접기 안에 넣는다는 뜻으로 해석했다.

## 원인
Quiz Bank는 출제 뒤 `quizbank/evidence.py`(핵심 근거 지면 선택 → 족보 지면 연결 → 족보 핵심 지면 선택)를
돌려 `validation`과 슬라이드 PNG로 올린다. Main-Quiz 생성(root generation)은 이 단계를 거치지 않고,
서버는 `bank_source == 'quizbank'`일 때만 Quiz Bank 근거를 붙인다(감염병리1은 `standalone`).

## Spec
- 생산(로컬, `quizbank/root_evidence.py`): 판의 `bank_snapshot`과 지문 확인된 원본 PDF(notes S1, exam S2)로
  Quiz Bank와 같은 함수(`slide_focus.select`, `jokbo_pages.connect`, `exam_focus.resolve`)를 돌려
  `root-evidence/1` JSON 하나를 만든다. 문항·판·학습 기록은 바꾸지 않는다.
  - 족보 번호→쪽: 공통 PDF 형식(docs/policies/jokbo-attachments.md)의 쪽 머리 `연도 | 교수 | N번`을
    고정 사본에서 읽어 색인한다(모델 없음). 감염병리1 S2(sha 82ba65c6, 27쪽)에서 25쪽이 색인된다.
  - S2 쪽 직접 인용(`physical PDF page 23`)도 같은 족보 칸으로 보낸다.
- 저장: 기존 asset 표의 새 종류 `root_evidence`, 파일명 `<revision>.json`. 스키마 변경 없음.
  러너의 기존 업로드 경로(`uploads` → R2 → `uploads/complete`)로 올린다. 새 종류는 작업을 만들지 않는다.
- 서버(`app/root_learning/evidence.py`): 판의 revision·원본 지문이 맞을 때만 읽는다.
  - `pdfSlides`: notes 출처만. Quiz Bank처럼 인용 쪽 ∪ 선택 쪽, `primary` 표시, 핵심 먼저.
  - `jokboPdfSlides`: exam 출처 쪽, `references`(「2023 김지은 79번」), `primary`(족보 핵심).
  - `evidenceStatus`, `conflict`(bank_snapshot.source_conflicts), `external`(EXT).
  - 근거 파일이 없거나 맞지 않으면 지금 동작(인용 쪽 그대로)을 유지하고 S2 쪽만 족보 칸으로 옮긴다.
- 화면(`RootSolve`·`RootPdfSlides`): 족보 핵심이면 족보 칸을 먼저. 핵심 슬라이드는 펼치고 나머지는
  「추가 참고 슬라이드 N장」. 근거 상태·충돌·EXT는 기존 「이 문항 검토 기록」 안(AnswerReviewItems).
- 러너: 뿌리 학습 결과 게시 직후 같은 고정 사본으로 근거를 만들어 올린다. 실패해도 게시는 그대로.

## 승인·보존
- 사용자의 작업 요청을 구현·배포 승인으로 본다(docs/development/README.md 「사람에게 묻는 것」 밖).
- 운영 쓰기는 근거 JSON 하나를 기존 업로드 API로 더하는 것뿐이다(되돌리기: asset 행·R2 객체 삭제).
- 모델 호출은 Quiz Bank 보강과 같은 경로(`coverage._call` → `studyez_llm.codex`, ChatGPT 로그인의 OpenAI Codex CLI)·같은 프롬프트, 같은 강의 자료다.
  (2026-11-09 정정: 처음 이 기록에 `claude -p`라고 적었으나 코드를 확인하지 않은 잘못이었다. 실제 호출은 처음부터 Codex CLI였다.
  사용자 지시 「CLI 작업은 openai에게 맡기자」와 일치하며 코드 변경은 없다.)

## 검사·결과
- quizbank `test_root_evidence` 3, runner `test_root_evidence_publish` 3 + 기존 generation 검사(근거 단계는 모델 없이 대체),
  server `test_main_quiz_reviewed_evidence`(핵심·족보·첨부 기출 핵심·상태·hash/판/지문 결속·충돌·EXT), web 렌더 4.
- 전체: contracts·quizbank·runner pytest 1,541 통과·1 실패(`test_desktop_control` 바로가기 설치기 — pristine master에서도 같은 실패,
  대시보드 기존 기록), server `-m tests`(PYTHONPATH=..) 129 전부 통과, web typecheck·build 통과.
- 기존 `web/tests/main-quiz-render.test.cjs`는 master에서도 `api.ts`의 `import.meta`·`platform/session` 로딩으로 실패한다(CI 밖). 고치지 않았다.
- 실제 데이터(감염병리1 261104_02 `map-tree-26110803`, 79문항): 보강 실행(OpenAI Codex CLI `gpt-6.1-sol`, 2회 315초·39초 — `usage.jsonl`, Quiz Bank 같은 프롬프트) 결과
  핵심 근거 single 69·linked 6·unresolved 4, 족보 색인 25쪽, 족보 연결 14문항, 족보 핵심 2문항.
  새 서버 코드로 모의(읽기만): 강의록 핵심 75문항, 족보 지면 14문항, 족보 핵심 2문항(그중 1은 강의록 첨부 기출 34쪽),
  근거 상태 4(자료 충돌 1·족보에만 2·근거 일부 부족 1).
- 모의 중 발견해 고친 것: 정리본 족보 사본의 파일명이 `….pdf (설명)`이라 PDF로 인정되지 않았다(스트림도 404였을 것) →
  `is_pdf`가 `.pdf` 뒤 설명을 허용. 강의록에 첨부된 기출이 족보 핵심인 경우 족보 칸으로 보낸다.

## 배포·운영 반영 순서
1. 코드 PR 병합 → API·웹 자동 배포(asset 종류 추가는 코드뿐, 스키마 변경 없음).
2. 배포된 API에 러너 업로드 경로로 `root_evidence/map-tree-26110803.json` 하나를 올린다.
3. 운영 정답 화면에서 감염병리1 근거 표시 확인.
롤백: PR revert. 근거 파일은 남아도 옛 코드는 읽지 않는다(필요하면 asset 행·R2 객체 삭제).
러너의 자동 보강은 새 코드를 쓰는 러너 프로세스부터 적용된다.
