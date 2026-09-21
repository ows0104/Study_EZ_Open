import { checklistItems, type AdminRow } from "../types";

/**
 * 관리 화면의 여러 탭이 같이 쓰는 셈들.
 *
 * 탭을 갈라 놓으면 같은 것을 두 곳에서 세게 된다 — 위 요약과 탭 이름 옆 숫자가
 * 그렇다. 세는 자리가 둘이면 언젠가 한쪽만 바뀐다.
 */

/** 아직 관리자 몫으로 남은 칸. `waived`는 닫은 것이므로 남은 것이 아니다. */
export function pending(row: AdminRow) {
  return checklistItems.filter((item) => row.checklist[item] === "todo");
}

/** 검토 표시가 남은 덱. 갈래(`pre`/`main`)와 함께 돌려준다. */
export function flaggedRuns(row: AdminRow) {
  return Object.entries(row.runMeta).filter(([, meta]) => meta.reviewFlagged > 0);
}

/** 시간표에 아예 못 붙은 편. */
export function isUnmatched(row: AdminRow) {
  return !row.match.timetableEventId;
}

/** 자동으로 붙었지만 사람이 아직 "맞음"을 안 누른 편. */
export function isUnconfirmed(row: AdminRow) {
  return Boolean(row.match.timetableEventId) && !row.match.confirmed;
}

/**
 * 러너가 살아 있는가. **자는 `jobProgress`로 옮겼다**(2026-09-21) — 학생의
 * 덱 칸까지 세 화면이 쓰게 되면서다. 여기 있던 값과 `DeckSlot`이 따로 들고
 * 있던 값이 우연히 같았다.
 */
export { RUNNER_STALE_MS, runnerAlive } from "../jobProgress";
