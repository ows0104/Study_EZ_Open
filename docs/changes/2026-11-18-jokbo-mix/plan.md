# 족보 모아풀기 — 구현 계획

## 변경 범위·대상 파일·순서
브랜치 `claude/jokbo-mix`(master f0ff4a97 기준).
1. `server/app/routes/jokbo.py`: `POST /jokbo/summaries`(R1·계약). `server/tests`: 요약 검사(보이는 칸만·관리자만 칸 숨김·없는 칸 빠짐·200개 상한), `test_route_contract.py`에 한 줄.
2. 새 `web/src/jokbo/jokboMix.ts`: 강의별 범위로 문항 고르기(기존 `pickItems` 재사용), 모아풀기 배분(R4), 섞어풀기, (칸, ID) 키.
3. `web/src/jokbo/JokboPage.tsx`: `JokboSolve`·`JokboDone`이 문항마다 그 강의 문서·칸을 쓰게 props 일반화하고 내보낸다. 강의 하나 화면은 같은 값을 넘겨 동작 그대로.
4. 새 `web/src/jokbo/JokboMix.tsx`(+ `jokbo.css` 몇 줄): 시작 화면(R3), 풀이·끝(R5), 회독(R6). `web/src/App.tsx` 경로 `/study/jokbo-mix`, `web/src/bank/mixLinks.ts`에 주소 함수.
5. `web/src/bank/StudyOverview.tsx`·`overview.css`: 족보 요약을 받아 체크 대상 넓히기(R1), 막대 단추 둘(R2). `BankBatch.tsx`: 단추별 이동.
6. 검사: 새 `server/tests/serve_jokbo_mix_fixture.py`(격리 sqlite·로컬 저장소, 합성 족보 두 칸), 새 `web/tests/jokbo-mix.*` 브라우저 검사,
   `scripts/check_root_learning.py`에 `jokbo-mix` 이름. 배분 규칙은 `jokboMix.ts` 단위 검사.

## 검사 명령과 성공 조건
- 서버: `server/`에서 `-m tests jokbo`(기존 족보 검사 포함), `route_contract` 통과.
- 웹: typecheck·build 통과.
- 브라우저(격리 fixture): 목록 체크 → 두 단추 → 족보 시작 화면, 전체/강의별 범위 칩·「일부」·같은 교수 없는 강의, 수 갱신,
  모아풀기 순서가 배분 규칙과 같음(문항 수 다른 두 강의), 섞어풀기에 모든 문항 한 번씩, 채점·표시가 각 칸으로 감, Z, 끝 화면, 회독 2건, 390px.
- 회귀: 강의 하나 족보 화면 기존 검사(있으면), `root-batch`(복습퀴즈 모아풀기 진입).

## 위험·복원·승인할 범위
- 승인 범위: 위 파일들의 로컬 구현·검사·PR. master 병합(=자동 배포)은 별도 승인.
- 위험: 목록이 족보 요약을 위해 칸 수만큼 R2 문서를 읽는다(첫 요청, 60초 캐시). 블럭 하나(수십 칸)에 한 번이며 행·▶는 기다리지 않는다.
- 위험: `JokboPage.tsx` props 일반화가 강의 하나 화면을 깨뜨릴 수 있다 — 브라우저 검사로 확인.
- 복원: git revert. 데이터 변경 없음.
