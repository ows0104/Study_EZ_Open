# 강의 패널 통계: 메모를 학습률 아래로 (2026-11-10)

## 사용자 지시 (2026-11-10)

강의 우측 패널 통계에서 「메모」가 「학습률」 위에 있다. 메모를 학습률 아래로 옮긴다.

## 바꾼 것

- `web/src/calendar/EventPanel.tsx`: 통계 섹션의 행 순서를 회독 → 학습률 → 메모 → 카드로 바꿨다.
  행 내용·스타일·API는 그대로 두었다.

## 겹침

- PR #86(`claude/panel-file-info`)도 `EventPanel.tsx`를 고친다. 다만 그쪽은 통계 섹션 아래(정보·덱 줄)를,
  이 작업은 통계 섹션 안을 고쳐서 충돌하는 부분이 없다. 사용자가 2026-11-10 「Go ahead on master」로 master에서 진행하기로 정했다.

## 검사

- `npm --prefix web run typecheck`, `npm --prefix web run build` 통과.
  빌드가 다시 만든 `web/public/bank-prompt.json`은 이 작업 것이 아니라서 되돌렸다.
- 브라우저 확인은 하지 않았다. 패널을 띄우려면 서버 API가 있어야 한다. 바꾼 것은 JSX 두 블록의 순서뿐이다.
