# 구현 계획

승인: 사용자 요청(2026-11-14) 자체가 이 범위의 구현 지시. master 병합(=자동 배포)은 별도 승인.

## 파일

1. `web/src/bank/RootSolve.tsx`: 고른 선지를 메모리에만 둔다. 문항이 바뀌면 비우고 `clearSavedPicks()`로
   `studyez:root-draft:*:picks`만 지운다. 모드 전환·선지 접기도 비운다. `:choices` 읽기는 그대로.
2. `web/tests/root-choice-keys.tsx`: 보관된 선택을 되살리지 않음·지움·다른 초안 유지·다시 열면 빈 선택.

## 검사

- `web/`에서 `npx tsc -b --noEmit`.
- vite(5199) 고정물 `root-choice-keys`, `choice-explanations`, `root-conflict-badge`.

## 위험·복원

- 새로고침하면 그 문항에서 고른 선지가 사라진다(의도). 복원은 `git revert`.
