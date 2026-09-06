import { checklistItems, type AdminRow, type RunnerBeat } from "../types";

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
 * 러너가 이 시간 안에 안 보이면 안 붙은 것으로 친다.
 *
 * 러너는 15초마다 서버에 물어보므로 2분은 넉넉하다. 넉넉하게 잡는 이유는 —
 * 짧게 잡으면 노트북이 잠깐 버벅인 것을 "꺼졌다"고 말하고, 그런 경고는 곧
 * 아무도 안 본다.
 */
export const RUNNER_STALE_MS = 120_000;

export function runnerAlive(runner: RunnerBeat | null | undefined): boolean {
  if (!runner?.lastSeen) return false;
  return Date.now() - new Date(runner.lastSeen).getTime() < RUNNER_STALE_MS;
}
