import type { DeckWatch, PrequizJob } from "./types";

/**
 * 「지금 무엇을, 몇 분째, 어디까지, 얼마나 남았나」를 한 줄로.
 *
 * 이 자리가 없던 동안 화면이 말할 수 있는 것은 「만드는 중」뿐이었다. 그래서
 * 5분째와 40분째가 같은 모양이었고, 멈춘 편과 오래 걸리는 편도 같은 모양이었다.
 *
 * **없는 값은 안 적는다.** 남은 시간은 지난 편들의 실측이 있어야 나오고
 * (`runner/eta.py`), 표본이 없으면 러너가 0을 올린다. 그때 「남은 약 0분」이라고
 * 적으면 그 뒤로 아무도 이 줄을 안 믿는다.
 *
 * 세 화면이 같이 쓴다 — 캘린더의 덱 칸(관리자·학생)과 `/admin`의 맨 위. 갈라
 * 두면 한쪽에 붙인 손질이 다른 쪽에 안 붙는다.
 *
 * **학생이 읽는 줄은 `watchLine`이 따로 짓는다.** 값은 같지만 할 수 있는 일이
 * 달라서다 — 자세한 것은 그 함수 머리에.
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
export function stageLabel(job: DeckWatch): string {
  const stage = job.stage || "시작";
  return job.stageTotal > 0 && job.stageIndex > 0
    ? `${stage} (${job.stageIndex}/${job.stageTotal}단계)`
    : stage;
}

/**
 * 도는 일감의 진행. `running`이 아니면 빈 문자열이다 — 줄 서 있는 일감의
 * `stage`는 서버가 넣어 둔 안내문이라 진행이 아니다.
 */
export function progressLine(job: DeckWatch, withStage = true): string {
  if (job.state !== "running") return "";
  // 단계 이름을 빼는 자리가 하나 있다 — **멈추는 중**. 그때는 부르는 쪽이 그
  // 사실을 앞에 적는데(서버도 `stage`에 같은 말을 넣어 둔다), 여기서 또 적으면
  // 한 줄에 같은 말이 두 번 선다.
  const parts = withStage ? [stageLabel(job)] : [];
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

/**
 * 모델 한도로 멈춰 기다리는 줄인가. 기다리면 되는 것과 사람이 손대야 하는 것을
 * 여기서 가른다.
 *
 * 2026-09-02에 한도에 두 번 걸렸는데(01:32·10:17) 둘 다 사람이 자거나 자리를
 * 비운 시각이었다. 그 편은 이제 실패로 죽지 않고 풀리는 시각까지 줄에 서 있다 —
 * **그 사실이 화면에 없으면 사람이 다시 누른다.**
 */
export function waitingUntil(job: DeckWatch): string {
  if (job.state !== "queued" || !job.resumeAt) return "";
  const when = new Date(job.resumeAt);
  if (Number.isNaN(when.getTime()) || when.getTime() <= Date.now()) return "";
  // **24시로 적는다.** 러너가 `stage`에 「13:40에 다시 시작」으로 적으므로, 여기서
  // 「오후 1:40」으로 그리면 같은 시각이 두 자리에서 다른 꼴이 된다.
  return when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

/** 아직 안 끝난 일감. `held`도 열려 있다 — 사람이 풀면 그대로 도는 줄이다. */
export function jobOpen(job: PrequizJob | null | undefined): boolean {
  return job?.state === "queued" || job?.state === "running" || job?.state === "held";
}

/** 화면이 계속 다시 읽어야 하는가. `held`는 사람을 기다리는 줄이라 안 움직인다. */
export function jobMoving(job: { state: PrequizJob["state"] } | null | undefined): boolean {
  return job?.state === "queued" || job?.state === "running";
}

/**
 * 러너가 이 시간 안에 안 보이면 안 붙은 것으로 친다.
 *
 * 러너는 15초마다 서버에 물어보므로 2분은 넉넉하다. 넉넉하게 잡는 이유는 —
 * 짧게 잡으면 노트북이 잠깐 버벅인 것을 「꺼졌다」고 말하고, 그런 경고는 곧
 * 아무도 안 본다.
 *
 * **이 자를 여기 둔 까닭은 이제 세 화면이 쓰기 때문이다** — `/admin` 맨 위,
 * 관리자의 덱 칸, 그리고 2026-09-21에 생긴 학생의 덱 칸. 앞의 둘이 각자 갖고
 * 있었고 값이 우연히 같았다.
 */
export const RUNNER_STALE_MS = 120_000;

export function runnerAlive(runner: { lastSeen: string } | null | undefined): boolean {
  if (!runner?.lastSeen) return false;
  return Date.now() - new Date(runner.lastSeen).getTime() < RUNNER_STALE_MS;
}

/**
 * 학생이 읽는 한 줄. **관리자의 `jobLine`과 같은 값을 다른 말로 적는다.**
 *
 * 2026-09-21 관리자 지시 — 「퀴즈를 만들고 있을 때 관리자가 아닌 사용자도
 * 사이드패널 현황을 볼 수 있게. 몇 단계 몇 분 남았는지.」
 *
 * **가르는 것은 「기다리면 되는가」 하나다.** 관리자의 줄은 그 위에 「무엇을
 * 해야 하는가」를 더 얹는다(노트북을 띄워라 · 다시 눌러도 소용없다). 학생은
 * 그 어느 것도 못 하므로, 그 말을 그대로 보여 주면 **자기가 뭘 잘못한 줄 안다.**
 *
 * 그래서 학생에게 안 적는 것이 있다 — 러너·일꾼·큐 같은 살림의 이름과,
 * **기다려도 안 오는 줄**(`held`, 러너가 꺼진 채 서 있는 줄). 뒤의 것은 빈
 * 문자열이라 부르는 쪽이 「아직 없습니다」를 그대로 둔다. 거기서 「곧 됩니다」로
 * 적으면 그 말이 며칠 간다.
 */
export function watchLine(job: DeckWatch, runner: { lastSeen: string } | null): string {
  const alive = runnerAlive(runner);
  if (job.state === "running") {
    // 만들다 멈춘 것을 「만드는 중」이라고 하면 안 된다 — 단계와 남은 시간이
    // 붙은 채로 굳어 있어서, 기다리는 사람은 그 숫자가 줄기를 기다린다.
    if (!alive) return `${stageLabel(job)}에서 멈춰 있습니다`;
    // 여기가 이 줄이 생긴 이유다 — 「② 카드 (6/17단계) · 12분째 · 남은 약 22분」.
    return `${job.force ? "다시 " : ""}만드는 중 · ${progressLine(job)}`;
  }
  // 모델 한도로 멈춘 편은 **저절로 이어진다.** 시각이 있으므로 러너가 지금
  // 안 보여도 적는다 — 그 사이에 노트북이 켜진다.
  const until = waitingUntil(job);
  if (until) return `${until}에 이어서 만듭니다`;
  if (job.state === "queued" && alive) return job.force ? "곧 다시 만듭니다" : "곧 만듭니다";
  return "";
}
