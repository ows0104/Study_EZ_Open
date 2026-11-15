# Main-Quiz: 세부를 묻기 전에 상위 연결의 존재를 묻는다 — 구현 계획

spec.md R1~R6를 PR 넷으로 나눈다. 각 PR은 혼자서 검사를 통과한다. 이미 공개된 판·학습 기록은 PR D의 실행 전까지 바뀌지 않는다.

## 설계상 확정한 것 (코드 조사 2026-11-15)

- **전제 판정은 별도 모델 단계다.** 이름은 `v4-presuppose`다.
  - coverage는 목표 묶음 단위로 돌고 「목표가 덮였나」만 본다. 새 목표를 만들 수 없고, 누락이 fix를 부르지도 않는다(`connection_generate_v4.py:375-414, 503`).
  - 그래서 전제 판정은 문항 전체(보이는 발문·정답)와 brief 목표를 받아 문항마다 `presupposes`를 낸다.
    각 행은 {A, B, relation_id?, covered_by_target?, recalled_by:[question_id]}다. 문항이 많으면 기존 chunked 틀로 나눈다.
- **회상되지 않은 전제는 기존 보충 경로를 탄다.** 이 경로는 이미 새 목표·관계를 만들고 지도 확인까지 한다.
  - 흐름: 새 포인트 → `v4-supplement-normalize` → `v4-coverage-supplement` → `v4-map-check-1`.
  - 그 뒤 add 루프(`ADD_LIMIT=2`)가 새 존재 목표의 문항을 쓴다.
  - 그래서 `v4-presuppose`는 첫 coverage·map-check(3단계) 직후, 보충(4단계) 앞에서 돈다. 이때 받는 문항은 front에서 들어온 문항이다.
  - add·fix가 나중에 쓴 문항의 전제는 다시 판정하지 않는다. 남은 전제는 판정 기록과 최종 문서로 `presuppose.report`가 센다(모델 호출 없음).
    구현 중 바꿨다: 보고만 위해 모델을 한 번 더 부를 이유가 없었다.
- **존재 목표의 관계는 내용 관계(association)다.** 처음 안은 `classification`이었다.
  하지만 지도 관계 검사(2026-11-14)는 classification만 가진 목표를 결함으로 본다. 그래서 연결 사실을 담은 내용 관계로 쓴다.
  보충 정규화는 기존 지도 관계만 쓸 수 있는데, 부모-자식 소속은 지도 관계가 아니다.
  그래서 `v4-supplement-normalize-presuppose`만 새 association(`RQP…`, unreviewed, 기존 개념 사이)을 더할 수 있게 했다.
  지도 확인이 그 관계를 판정한다.
- manifest `presuppositions`는 선택 키다. 이전 결과에는 없으므로 `MANIFEST_KEYS`(필수 키)에 넣지 않았다.
- **선행 연결은 판정 기록에서 코드가 결정적으로 만든다.**
  - 지금 검증 조건(`roots/validate.py:46-57`, `generation_v4.py:916` `make_document`)은 다음을 요구한다.
    - kind=prerequisite 관계가 있고, review_status가 reviewed이며, 지도 확인 supported다.
    - 관계의 from은 before 목표의 개념, to는 after 목표의 개념이다.
    - 순환이 없다.
  - 새 관계를 지도 확인 뒤에 더할 수 없다(`extend_brief`). 따라서 `v4-presuppose` 판정을 선행 관계의 근거로 인정하는 정책을 하나 더한다.
    - 원본 사실이 아니라 학습 순서이므로 지도 확인 대신 이 판정이 근거다.
    - 관계와 간선은 `make_document`가 저장된 판정에서 다시 만들어, 재조립 일치(`again == doc`)를 지킨다.
  - from/to 개념을 어떻게 고를지는 PR A 첫 단계 시제품에서 정한다. 존재 목표와 세부 목표가 같은 개념 B를 공유하면 자기 고리가 생기기 때문이다.
- **상위 연결 관계의 종류.** 정규화가 만드는 존재 목표의 관계는 enum에 이미 있는 `classification`을 쓴다.
  지도 관계 검사(`generation_v4.py:202`)는 classification만 가진 목표를 결함으로 본다. 존재 목표에서는 이것을 결함으로 보지 않게 한다.
  새 kind를 더하지 않으니 brief·정규화·지도 확인 스키마가 바뀌지 않는다.
- **지도 화면.** `web/src/bank/rootMapTree.ts:41-57`·`RootMap.tsx:95-100`는 모든 관계를 가로 연결로 그리고, 답 노드 판정에도 쓴다.
  `prerequisite`는 순서 기록이므로 둘 다에서 뺀다. 빼지 않으면 존재 목표의 답 노드가 주제 노드로 바뀐다.
  `classification`은 빼지 않는다. 공개된 판에 이미 176개가 있고 모두 트리 부모-자식과 같은 관계라, 빼면 기존 지도가 바뀐다.
  대신 정규화가 존재 목표의 소속 관계를 트리 간선 그대로(실제 부모 → 자식) 쓰게 해, 기존 classification과 같은 모양으로 둔다.
- **정책 기록.** 새 실행 장부(`fresh`)에만 `presuppositions: 'presuppose/1'`을 넣는다. 옛 장부는 지금 동작을 유지한다.
  manifest에 `presuppositions` 키를 더하고 `MANIFEST_KEYS`와 `_judgments4`에서 검사한다.

## 변경 범위·대상 파일·순서

### PR A — 새 출제 경로 (R1·R2 간선·R3·R4·R5)
1. 시제품(테스트 우선): `tests/quizbank/test_presuppose.py`에 가짜 모델로 다음 흐름을 세운다.
   「발문이 A→B를 주고 C를 묻는 문항 하나 + 목표 하나」 → 전제 누락 → 보충 → 존재 목표·문항 → 선행 간선.
   여기서 선행 관계의 from/to 선택 규칙을 정한다.
2. 계약 `studyez_contracts/roots/generation_v4.py`
   - `PRESUPPOSE_OUTPUT` 스키마, `check_presuppose`(ID·문항 존재·recalled_by가 실제 정답인지 형식 검사)
   - 회상되지 않은 전제를 보충 포인트로 바꾸는 함수
   - 판정에서 선행 관계·간선을 만드는 함수(`make_document`에서 호출)
   - classification만 가진 존재 목표를 결함에서 빼기
   - `MANIFEST_KEYS`
   - 선행 근거 정책은 `roots/validate.py`에서 인정한다.
3. 생성기 `quizbank/connection_generate_v4.py`
   - `fresh`에 정책 추가
   - 3단계 뒤 `v4-presuppose`(chunked), 결과를 4단계 보충 입력에 합치기
   - 마지막 coverage 뒤 보고용 재판정(`v4-presuppose-final`)
   - manifest 기록
4. 러너 `runner/root_native_json.py`: 새 단계의 스키마·검사·프롬프트 선택(`v3_schema`·`v3_check`·`task_for`).
5. 프롬프트
   - `content/prompts/learning-links/v4/presuppose.md`(새): spec 용어 그대로. 증례 단서는 전제가 아니다.
     기능 단서로 이름을 답하게 한 문항도 회상으로 센다.
   - `v4/normalize.md`: R1 의존 기준, 존재 목표, 쪼갤 때 상위 질문 먼저, 지어낸 묶음 이름 금지
   - `v4/add.md`·`fix.md`·`item-review.md`: R4
   - `v4/supplement-normalize`(해당 파일): 전제에서 온 포인트는 존재 목표로 정규화
6. 측정 도구 `quizbank/presuppose_report.py`(R5, 모델 호출 없음)
   - 결과 하나를 받아 전제·회상·선행·존재 목표·문항 증가를 낸다.
   - 정책이 없는 옛 결과에는 문자 대조 근사(intent의 거친 측정)를 쓴다.
7. 문서: `quizbank/CLAUDE.md` 단계 목록, `docs/map.md`에 필요하면 한 줄.

### PR B — 지도 화면 (R2의 화면 영향)
8. `web/src/bank/rootMapTree.ts`·`RootMap.tsx`: `contentRelations`로 가로 연결·답 노드 판정에서 `prerequisite`만 뺀다.
   공개된 판에는 prerequisite 관계가 0개라 기존 지도는 바뀌지 않는다. `web/tests/main-quiz-map-tree.test.cjs`에서 확인한다.

### PR C — 학습 계획 (R2 복습에서 풀어 주기)
9. `server/app/root_learning/planning.py` `plan_tasks`
   - 선행 끌어오기 조건을 `not learned`에서 바꾼다. 새 조건: 학습 전이거나, 존재 목표의 최근 평가가 `independent`가 아니고 오늘 이미 풀지 않았을 때 끌어온다.
   - `replay_tasks` 행의 `rating`(과제별 최근 평가 중 가장 낮은 것)과 `lastDay`를 쓴다.
   - /2·/3 `plan()`은 새 문서가 나오지 않으므로 그대로 둔다.
10. `server/tests/test_root_planning.py`·`test_root_prereq_closure.py`에 경우를 더한다.
    - missed → 앞에 끌어옴
    - independent → 끌어오지 않음
    - 같은 날 → 끌어오지 않음
    - 선행 없는 판 → 동작 같음

### PR D — 공개된 강의 보강 경로 (R6, PR A 위에 쌓은 브랜치)

사용자 「처음부터 재출제는 에바, 새출제는 이걸로 하고 옛날꺼는 보강만」(2026-11-15). 그래서 실측 3편의 새 출제는 하지 않는다.
대신 PR D를 PR A 위에 바로 이어 만들고, 공개된 강의 한 편의 로컬 사본에 보강을 돌려 실측을 겸한다.

구현에서 정한 것:
- 이 경로는 공개된 판이 쓰지 않은 단계만 돈다.
  - 전제 판정(`v4-presuppose-<k>`, 기존 문항 전부)
  - 존재 목표(`v4-supplement-normalize-presuppose`·`v4-coverage-presuppose`·`v4-map-check-presuppose`)
  - 새 문항 출제(`v4-add-presuppose-<n>`, ≤2)
  - 새 문항 검토·고치기(`v4-review-presuppose-<k>`·`v4-fix-presuppose-<k>`, ≤2)
  - 새 문항만 의학 검토(`medical-presuppose`)
- 일반 /4 생성을 이어 가기로 다시 돌리지 않는다. 빈 목표가 바뀌면 `v4-add-0` 입력이 달라져 기존 추가 문항을 다시 쓰기 때문이다.
- **의학 검토 예외.** 결과 계약은 「의학 검토는 마지막에 은행 전체를 한 번」이다(`medical-0` 입력 = 최종 은행).
  문항을 더하면 전체를 다시 검토해야 하고, 그러면 공개된 판정이 새 판정으로 바뀐다.
  그래서 presupposeOnly 기록이 있는 결과만 다르게 검사한다(`generation_v3._check_backfill_medical`).
  - 이전 의학 검토(출력 지문으로 증명)
  - 새 문항만의 의학 검토(입력·출력 지문으로 증명)
  - 저장된 의학 검토 행은 둘을 은행 순서로 합친 것과 정확히 같다.
- **새 문항은 임상 충돌 기록을 더하지 않는다.** 공개된 판의 맥락 판정은 충돌 기록마다 한 번이고, 이 경로는 그것을 다시 하지 않는다.
  더하면 단계 검사가 거절하고 모델 세션 안에서 다시 쓰게 한다.
- 근거(root evidence)는 이전 판 것을 재사용하지 않고 새로 만든다. 새 문항이 있기 때문이다.

계획 당시 문항:
11. 새 `quizbank/connection_presuppose.py`(`presuppose-only/1`): `connection_replace.py`와 같은 seed 검사로 공개 실행을 이어받는다.
    - `v4-presuppose`를 기존 문항 전부에 돌린다.
    - 새 존재 목표만 보충 → add → review/fix → coverage → 의학 검토를 거친다.
    - 선행 간선을 만든다.
    - 공개된 지도는 다시 판정하지 않는다. 기존 문항은 빼지 않는다.
12. 연결
    - `quizbank/connection_generate.py`: `run(..., presuppose_of=)`, `--presuppose-of`
    - `runner/connection_generation.py`: `duplicates_front` 재사용, 인자 전달
    - `server/app/routes/root_generation.py`: 요청 필드 `presupposeOnly`(기존 두 플래그와 같은 조건, 셋 중 하나만)
13. `tests/quizbank/test_connection_presuppose.py`(새), 서버 요청 검증, 러너 분기 테스트.

## 검사 명령과 성공 조건
- `python -m pytest tests/contracts tests/quizbank tests/runner -q` 통과(알려진 환경 실패는 따로 적는다).
- 서버: `server/`에서 `.venv/Scripts/python.exe -m tests root`. `PYTHONPATH=..`과 격리된 로컬 DB를 쓰고, 운영 `.env`는 쓰지 않는다.
- 웹: `tsc --noEmit` 변경 파일 오류 없음. 기존 공개 판 두 편의 지도 화면 전후 사진 같음.
- 실측(로컬 실행, 공개하지 않음). 과목 성격이 다른 3편을 새로 출제한다.
  - 후보: 콜레라·캄필로박터·수도모나스(세균), 간염바이러스 또는 피코르나(바이러스), 항생제 약리학의 기본 원리(약리)
  - R5 도구로 전후를 비교한다. 성공 조건:
    - 회상되지 않은 전제가 예외 외 0이다.
    - 전제가 있는 목표는 모두 선행을 가진다.
    - 지어낸 묶음 이름이 없다.
  - 문항 수 증가·모델 호출 수·시간을 보고한다.
- 실측(R6, PR D 뒤). 공개 실행 한 편의 로컬 사본에 보강을 돌린다. 성공 조건:
  - 기존 과제가 전부 유지된다.
  - 새 모델 단계는 전제 판정과 새 목표 관련 단계뿐이다.
  - 회상되지 않은 전제가 줄어든다.

## 위험·복원
- **문항 수 증가.** 존재 목표만큼 늘어난다(의도). 실측에서 편당 증가를 보고한다. 과하면 R1 기준을 조인다.
- **모델 비용.** 편당 `v4-presuppose` 1~수 회와 보충·add 라운드가 는다. 실측에서 잰다.
- **과잉 전제.** 모델이 사소한 것까지 전제로 낼 수 있다. 판정 기준 문장(증례 단서 제외 등)과 실측 목록을 직접 읽어 조정한다.
  추측으로 기준을 굳히지 않는다.
- **다른 작업과 겹침**(대시보드).
  - supplement-point-ids PR #154(`generation_v4.py` attach_points)가 병합된 뒤 rebase한다.
  - unplaced-replace(`connection_generate_v4.py` 늦은 보충·`connection_replace.py`)는 남은 운영 실행만 있으므로 코드는 병합본 위에서 시작한다.
  - 공개판 교체(PR D 실행)는 재배치와 강의별로 차례로 한다.
- **복원.** PR revert로 되돌린다. 새 정책은 새 장부에만 기록되므로, 옛 실행의 이어 가기는 영향이 없다.
  R6 교체는 이전 판으로 다시 교체할 수 있다(이전 실행 폴더 보존).
- 기존 출제·검수 상한은 재실행으로 초기화하지 않는다.

## 승인할 범위
- 이번 요청(「plan 작성」)은 계획 작성까지다.
- 구현 승인을 받으면 PR A~C의 구현·검사·Draft PR까지 진행한다.
- 따로 묻는 것
  - 실측 3편의 로컬 새 출제: 모델 호출이 많고 러너 PC 시간을 쓴다.
  - 병합(master 병합은 API·웹 자동 배포)
  - PR D 구현 시작(PR A 병합 뒤)
  - 공개판 보강 실행(편마다, 보고 뒤)
