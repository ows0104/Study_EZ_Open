# 족보 모아풀기 — 배포 준비

## 코드 리뷰·검증 결과
- 서버(격리 sqlite·로컬 저장소): `jokbo`(새 `POST /jokbo/summaries`: 보이는 칸만, 겹침·모양 틀린 ID 빠짐, 0·201개 422, 관리자만 족보는 학생에게 안 보임)·
  `route_contract`(한 줄)·`timetable` 통과.
- 웹: typecheck·build 통과.
- 브라우저(`check_root_learning.py --check jokbo-mix`, 합성 족보 세 칸 6+2 / 2+1 / 0+1) 2개 통과:
  범위 칩 전체·강의별·「일부」·같은 교수 없는 강의(같은 교수만 0·꺼짐), 수 갱신, 모아풀기 순서가 (k+½)/n 배분과 같음
  (A1 A2 B1 A3 C1 A4 A5 B2 A6), 머리줄 강의 제목, Z, 채점이 각 칸·원래 ID로(9건), 회독 3칸, 끝 화면 오답노트, 섞어풀기 모든 문항 한 번씩, 390px.
- `study-mix-pick` 2개 통과(족보만 있는 칸 체크, 막대 두 단추, 족보 단추가 칸 ID를 목록 순서·중복 없이 실음). 막대 390px 두 줄 확인.
- 회귀: `root-batch` 2개, `jokbo-selection` 5개, 강의 하나 족보 `jokbo-undo` 자체 검사 ALL PASSED.
- 기존 실패(이번 변경과 무관, master도 같음): `study-management.test.cjs` 76행.
- 계획과 다른 점: 배분 모듈 이름을 `jokboMix.ts` 대신 `web/src/jokbo/mixOrder.ts`로 했다(Windows에서 `JokboMix.tsx`와 대소문자만 달라 tsc가 거절).
  단위 검사 대신 브라우저 검사가 배분 순서를 정확히 확인한다.

## 배포 대상 버전·순서·데이터 변경
- 대상: `claude/jokbo-mix`(master f0ff4a97 기준). DB·족보 문서·R2 변경 없음.
- 서버(새 읽기 경로)와 웹이 같이 바뀐다. 자동 배포 순서(API 먼저 → 같은 SHA 웹). 웹이 먼저 나가면 요약 요청이 실패해 족보만 있는 칸의 체크가 안 보일 뿐이다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 강의 목록에서 족보가 있는 강의 둘 체크 → 「족보 모아풀기」 → 수·칩, 한 문항 풀고 오답노트에 그 강의로 남는지.
- 롤백: git revert. 데이터 변경 없음.
- 필요한 승인: master 병합(=운영 자동 배포)은 사용자 승인 후.
