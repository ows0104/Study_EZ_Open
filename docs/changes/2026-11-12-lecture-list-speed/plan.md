# 강의 목록 정보 먼저 보이기 — 구현 계획

## 변경 범위·대상 파일·순서
1. `web/src/bank/useStudyTimetable.ts` — study-progress 단계 제거.
2. `web/src/bank/useRootCatalog.ts` — `useRootSummaries`(loaded 포함)·`prefetchRootCatalog`.
3. `web/src/bank/StudyOverview.tsx` — 행·▶를 시간표로, 숫자 칸만 요약 대기(「…」).
4. `web/src/bank/BankBatch.tsx` — 페이지 진입 때 요약 미리 출발, `onScope` 제거.
5. `web/src/bank/overview.css` — `is-loading` 흐린 숨쉬기(움직임 줄이기 설정 존중).
6. `web/tests/study-management.tsx`(`?lazy`에만 Main-Quiz 표시·요약 응답 붙잡기), `web/tests/study-loading.test.cjs` 다시 씀.

## 검사 명령과 성공 조건
- `tsc -b web --noEmit` 종료 0.
- `web/tests/study-loading.test.cjs` 2건 통과: 요약을 붙잡은 동안 행 10개·▶ 켜짐·「…」 70칸·study-progress 0회, 풀면 숫자 채움, 블럭 바꿔도 요약 재요청 없음, 실패 시 「—」.
- `study-management.test.cjs`·`quiz-publication.test.cjs`의 기존 실패 2건(「퀴즈 없음」 문구·프롬프트 1.99)은 master에서도 같은 2건이 실패한다 — 이 작업과 무관, 그대로 둔다.

## 위험·복원·승인할 범위
- 위험: 요약이 늦는 동안 위 통계가 「…」로 보인다(전에는 「—」). 요약 자체 시간은 그대로다.
- 복원: git revert(웹만). 승인 범위: 사용자 요청 원문의 강의 목록 표시 순서 변경, 위 파일들.
