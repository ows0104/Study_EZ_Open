import type { AdminOverview } from "../types/admin";
import type { JobBoard, PrequizJob } from "../types/jobs";
import { jobMoving } from "../jobProgress";

export const ADMIN_REFRESH_MS = 10 * 60_000;

/** Returning to a tab must not turn repeated tab switches into extra polling. */
export function refreshDue(lastFetchedAt: number, now = Date.now()): boolean {
  return now - lastFetchedAt >= ADMIN_REFRESH_MS;
}

/** Progress updates don't require reloading bank contents or review reports. */
export function mergeJobBoard(overview: AdminOverview, board: JobBoard): AdminOverview {
  const latest = new Map<string, PrequizJob>();
  for (const job of board.jobs) {
    const key = JSON.stringify([job.subject, job.runId]);
    if ((latest.get(key)?.id ?? -1) < job.id) latest.set(key, job);
  }
  return {
    ...overview,
    runner: board.runner,
    lectures: overview.lectures.map((row) => {
      const job = latest.get(JSON.stringify([row.subject, row.runId]));
      return job && job.id >= (row.prequizJob?.id ?? -1) ? { ...row, prequizJob: job } : row;
    }),
  };
}

/** Refresh uploaded results once when a job finishes, fails, or pauses for input. */
export function resultsChanged(previous: JobBoard | null, next: JobBoard): boolean {
  if (!previous) return false;
  const before = new Map(previous.jobs.map((job) => [job.id, job]));
  const after = new Map(next.jobs.map((job) => [job.id, job]));
  return previous.jobs.some((job) => jobMoving(job) && !jobMoving(after.get(job.id))) ||
    next.jobs.some((job) => !jobMoving(job) && job.state !== "held" && before.get(job.id)?.state !== job.state);
}
