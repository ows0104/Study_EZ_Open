import type { PrequizJob } from "./types";

/**
 * 「지금 무엇을, 몇 분째, 어디까지, 얼마나 남았나」를 한 줄로.
 *
 * 이 자리가 없던 동안 화면이 말할 수 있는 것은 「만드는 중」뿐이었다. 그래서
 * 5분째와 40분째가 같은 모양이었고, 멈춘 편과 오래 걸리는 편도 같은 모양이었다.
 *
 * **없는 값은 안 적는다.** 남은 시간은 지난 편들의 실측이 있어야 나오고
 * (`studyez/eta.py`), 표본이 없으면 러너가 0을 올린다. 그때 「남은 약 0분」이라고
 * 적으면 그 뒤로 아무도 이 줄을 안 믿는다.
 *
 * 두 화면이 같이 쓴다 — 캘린더의 덱 칸과 `/admin`의 맨 위. 갈라 두면 한쪽에
 * 붙인 손질이 다른 쪽에 안 붙는다.
 */

/** 초를 사람 말로. 1분 미만은 초로 — 방금 시작한 것이 「0분」으로 보이면 멈춘 것 같다. */
export function humanSeconds(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "";
  if (seconds < 60) return `${Math.round(seconds)}초`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}분`;
  return `${Math.floor(minutes / 60)}시간 ${minutes % 60}분`;
}

/** 몇 번째 단계인가. 차례를 모르면(0/0) 단계 이름만 남는다. */
export function stageLabel(job: PrequizJob): string {
  const stage = job.stage || "시작";
  return job.stageTotal > 0 && job.stageIndex > 0
    ? `${stage} (${job.stageIndex}/${job.stageTotal}단계)`
    : stage;
}

/**
 * 도는 일감의 진행. `running`이 아니면 빈 문자열이다 — 줄 서 있는 일감의
 * `stage`는 서버가 넣어 둔 안내문이라 진행이 아니다.
 */
export function progressLine(job: PrequizJob): string {
  if (job.state !== "running") return "";
  const parts = [stageLabel(job)];
  const elapsed = humanSeconds(job.elapsedSeconds);
  if (elapsed) parts.push(`${elapsed}째`);
  const stuck = humanSeconds(job.stageSeconds);
  // 한 단계에 5분 넘게 머무는 것은 정상이다(「② 카드」가 편의 절반이다). 다만
  // 그 사실이 안 보이면 멈춘 것과 구별되지 않는다.
  if (stuck && job.stageSeconds >= 300) parts.push(`이 단계 ${stuck}째`);
  const left = humanSeconds(job.etaSeconds);
  if (left) parts.push(`남은 약 ${left}`);
  return parts.join(" · ");
}

/** 아직 안 끝난 일감. `held`도 열려 있다 — 사람이 풀면 그대로 도는 줄이다. */
export function jobOpen(job: PrequizJob | null | undefined): boolean {
  return job?.state === "queued" || job?.state === "running" || job?.state === "held";
}

/** 화면이 계속 다시 읽어야 하는가. `held`는 사람을 기다리는 줄이라 안 움직인다. */
export function jobMoving(job: PrequizJob | null | undefined): boolean {
  return job?.state === "queued" || job?.state === "running";
}
