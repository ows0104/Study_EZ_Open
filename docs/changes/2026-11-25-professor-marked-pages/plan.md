# 교수가 짚은 쪽을 Core 이상으로 빠짐없이 — 구현 계획

사용자 요청 원문(2026-11-25): 「spec부터 써」, 결정 다섯(spec 「사용자 결정」), 「지금 2차만 하면 돼. 그리고 Must-know는 좀 그렇고 Core 이상으로 하자.」, plan 요청 「어 하자」.

## 미리 확인한 구조 (origin/master e8dd0c32)

- **앞 단계**
  - `runner/root_front.py`가 map-tree/3 앞 단계를 돌린다. 순서는 map → point → audit → repair → final-audit → derive다.
  - 포인트 추출 지시문은 `point-extract-v4.md` 뒤에 `map-tree/extract-task.md`를 붙인 것이다. 출력 형식은 `point-output-v4.schema.json`이다.
  - 검토·보완 지시문은 `point-audit-v4.md`·`point-repair-v4.md`다.
  - `notebook_profile`은 포인트 문서에 실린다. 생성기는 `generation_v4.notebook_profile(packet, meta)`로 읽는다.
- **등급**
  - `generation_v4.assemble` → `question_table` → `importance.score` 순서로 계산한다.
  - assemble은 러너와 서버가 같이 쓴다. 서버는 받은 결과를 `automation.validate_result` → `generation_v4.validate_result`로 다시 조립해 대조한다.
    그래서 계산 규칙이 바뀌면 **서버에 먼저 배포**해야 한다. 옛 판은 옛 규칙으로 계속 통과해야 한다.
- **보강**
  - 보강(presuppose-only/1)은 공개판 위에 보충 포인트를 덧붙인다(origin: question·presuppose·discriminate).
  - 이때 `notebook_profile`이 바뀌면 거부한다(`result4: supplement changed the exam points`).
  - 채우기 기록은 `runs/fill-goals.json` → 실행 폴더 `fill.json`으로 굳힌다(`runner/fill_goals.py`).

## 변경 범위·대상 파일·순서

정책 문구를 바꾸는 단계마다, 기준 fixture를 같은 커밋에서 바꾼다(map-tree README 「문구는 출제 정책이다」).

1. **계약: `marked_pages`와 등급 하한** — `studyez_contracts/`
   - `bank/importance.py`
     - `POLICY2 = "importance-basis/2"`를 둔다.
     - `score`·`question_table`이 `marked`(질문 ID 집합)를 받는다.
       계산 결과가 Core 미만이면 Core로 올리고 `rule: "marked_page"`로 적는다.
     - `exam_exclusion`은 그대로 Optional이다.
     - /1 호출은 결과가 바뀌지 않는다.
   - `roots/generation_v4.py`
     - `check_points`: `notebook_profile.marked_pages`의 모양을 검사한다(선택 칸).
       - `instruction.quote`·`refs`·`year`·`source`
       - `pages`의 쪽 범위
       - `marked: true` 포인트의 근거 쪽이 짚은 쪽 안에 있는가
     - `marked_questions(brief, coverage_rows, points)`: `marked` 포인트에서 나온 목표의 component를 `location=answer`로 묻는 문항 ID를 코드로 모은다.
     - `assemble`: `marked_pages`가 있을 때만 /2로 계산한다. 없으면 지금과 글자 하나 다르지 않다.
       결과 meta에 `importancePolicy`를 남긴다. `validate_result`는 그 값대로 다시 계산한다.
     - `notebook_profile`(보강 검사): 원래 프로필에 `marked_pages`만 더해진 경우를 허용한다.
       이때 근거는 관리자 기록이고 `source: "admin"`이다.
   - `importance_warnings`: `marked_page`로 올라간 문항 수를 따로 보고한다.
2. **앞 단계 지시문과 형식** — `content/prompts/learning-links/`
   - `point-output-v4.schema.json`
     - `notebook_profile.marked_pages`(선택)를 더한다.
     - 포인트에 `marked`(선택, boolean)를 더한다.
   - `point-extract-v4.md`
     - 교수가 특정 표시·쪽을 「시험은 여기」·「이것만 외우면」·「중점」으로 짚은 말씀이 있으면 `marked_pages`를 쓴다.
       원문과 쪽, 연도를 함께 적는다.
     - 필기자 자신의 표시는 쓰지 않는다.
     - 짚은 쪽의 정보는 모양(본문·표·도식·그림)과 상관없이 빠짐없이 포인트로 뽑고, `marked: true`를 단다.
     - 묶음 모양은 원본 묶음 규칙을 따른다.
   - `map-tree/point-audit-v4.md`: `marked_pages`의 인용·빠진 쪽·잘못 넣은 쪽, 짚은 쪽 안의 빠진 정보를 `missing`으로 지적한다.
   - `map-tree/point-repair-v4.md`: 위 지적을 채운다.
   - fixture: `tests/fixtures/map_tree_*` 중 v4 기준본을 갱신한다.
3. **관리자 지정 길** — `content/prompts/bank/markedPages.json`(새 파일), `runner/root_front.py`, `runner/marked_pages.py`(새 파일)
   - 형식
     ```json
     {"version": 1, "lectures": {"<과목>/<runId>": {
       "pages": [...], "marker": "…", "note": "…", "year": 2026,
       "approval": "사용자 발언 원문", "at": "ISO"}}}
     ```
   - 새 출제: 앞 단계 `prepare`가 이 기록을 실행 폴더에 굳힌다(`fill.json`과 같은 방식).
     포인트 추출 입력에 「관리자가 지정한 짚은 쪽」으로 넣는다.
     추출 결과의 `marked_pages`는 관리자 값으로 덮는다(`source: "admin"`).
   - 보강: 생성기가 굳힌 기록을 `notebook_profile.marked_pages`로 더한다.
   - 작년 필기에만 근거가 있는 경우(결정 3)
     - 추출이 `year` < 올해로 쓰면 등급에 쓰지 않는다.
     - 보고서에 「관리자 확인 필요」로 남긴다.
     - 관리자가 이 파일에 적으면 적용된다.
   - 사이트 관리자 화면 입력은 이번에 만들지 않는다(서버·DB 변경이 필요하다). 필요하면 다음 작업으로 한다.
4. **보강으로 빈 곳 채우기** — `quizbank/connection_presuppose.py`, `content/prompts/learning-links/v4/point-supplement.md` 또는 새 `v4/marked-supplement.md`
   - 보강 실행에서 `marked_pages`가 있으면 짚은 쪽 쪽 이미지와 지금 포인트·목표를 함께 보낸다.
     모델이 빠진 정보를 보충 포인트(origin `marked`, `marked: true`)로 적는다.
   - 그다음은 지금 보강 흐름(목표 → add → 검토 → 커버)을 그대로 탄다.
   - 기존 공개 문항은 고치지 않는다. 새 정보는 새 문항으로만 더한다.
   - 이미 있는 문항의 등급은 조립 때 /2로 다시 계산된다. 짚은 쪽 답이면 Core 이상이 된다.
   - `generation_v4.notebook_profile`의 보충 origin 목록에 `marked`를 더한다.
5. **보고** — `quizbank/connection_generate_v4.py`
   - `readiness.json`과 출력 줄에 짚은 쪽마다 목표 수·covered·Core 이상 문항 수를 남긴다.
   - 짚은 쪽인데 목표가 0개면 경고만 하고, 게시는 막지 않는다.

배포 순서는 1(서버 배포, master 병합) → 2·3·5(러너 재설치) → 4(러너 재설치)다.
1~5는 한 PR로 두되, 병합 뒤 러너 재설치 전에 라이브 API가 새 커밋인지 확인한다.

## 검사 명령과 성공 조건

로컬(이 worktree, `PYTHONPATH=.`, anaconda python):

- `python -m pytest tests/contracts/test_importance_basis.py tests/contracts/test_tier_from_importance.py tests/contracts/test_generation_v4.py`
  - 새 시험
    - /2 하한(Important → Core, Optional → Core, Essential 유지, exclusion은 Optional 유지)
    - `marked_pages`가 없으면 /1과 같다
    - `check_points` 모양 오류
    - `marked_questions`가 answer 위치만 센다
    - 보강의 profile 허용 범위
- `python -m pytest tests/runner/test_root_front.py tests/runner/test_root_front_v3.py tests/runner/test_fill_goals.py`
  - fixture 갱신
  - `markedPages.json` 굳히기와 형식 오류
- `python -m pytest tests/quizbank/test_root_generation_v4.py tests/quizbank/test_connection_presuppose.py`
  - 보강 origin `marked`
  - 조립에서 /2 적용
- 회귀(state.json `regression`)
  - `python -m pytest tests` 전체
  - 서버 파일별 검사 중 root_generation·generation_import(`docs/commands.md` 「검사」)
  - **이미 받은 공개 v4 결과 하나를 새 코드의 `validate_result`로 다시 통과시킨다.** 예: 루프스 261123_06 최신판. 옛 판 호환 확인용이다.
- 시범(운영 쓰기, 시작 전 사용자 확인)
  - 전신경화증 261124_01 올해 원본에서 햇살 쪽을 다시 센다.
  - `markedPages.json`에 기록한 뒤 보강 요청을 낸다.
  - 성공 조건
    - 햇살 쪽 정보마다 Core 이상 문항이 있다(사람이 쪽마다 대조해 표로 남긴다).
    - 공개 문항 ID와 학습 기록이 이어진다.
    - 햇살 밖 문항의 등급이 변하지 않는다.

## 위험·복원·승인할 범위

- **서버 재검증**
  - 계약 변경이 옛 결과의 재조립을 바꾸면 이미 게시된 판의 가져오기와 재검증이 깨진다.
  - 그래서 /2는 `marked_pages`가 있을 때만 쓴다. 옛 판 재검증 회귀를 필수로 돌린다.
- **출제 정책 문구**: 추출·검토 지시문은 모든 강의에 들어간다. 짚은 쪽 말씀이 없는 강의에서는 출력이 바뀌지 않아야 한다.
  2차의 다른 강의(예: 루프스) 하나를 앞 단계만 다시 돌려, 그 강의에 `marked_pages`가 생기지 않는지 본다.
- **겹침**: 긴 나열 답 작업이 `connection_presuppose.py`를 바꿨다(#258 병합). 4번은 병합된 master 위에서 하고, 구현 전에 대시보드를 다시 본다.
- **복원**
  - 코드는 revert 커밋 하나로 되돌린다.
  - 운영은 보강판을 잘못 올렸을 때 이전 공개판으로 되돌리는 기존 절차를 쓴다(docs/deployment.md).
  - `markedPages.json` 기록을 지우면 다음 출제부터 원래대로 돈다.
- **승인할 범위**
  - 위 1~5의 로컬 구현과 검사
  - PR(Draft) 생성
- **따로 승인받을 것**
  - Ready·병합(= 서버·웹 자동 배포)
  - 러너 재설치
  - 전신경화증 보강 운영 요청
