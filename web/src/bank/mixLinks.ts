/** Main-Quiz 모아풀기 주소(2026-11-18). 고른 강의가 주소에 그대로 남아 새로고침·뒤로에도 같은 묶음이 열린다. */
export type MixLecture = { subject: string; runId: string };

export const MIX_PATH = "/study/mix";

export function mixHref(lectures: MixLecture[]) {
  const params = new URLSearchParams();
  for (const l of lectures) params.append("l", `${l.subject}/${l.runId}`);
  return `${MIX_PATH}?${params.toString()}`;
}

/** `l=<subject>/<runId>`를 고른 순서대로 읽는다. 겹치거나 모양이 틀린 값은 뺀다. */
export function readMix(params: URLSearchParams): MixLecture[] {
  const seen = new Set<string>();
  const out: MixLecture[] = [];
  for (const value of params.getAll("l")) {
    const cut = value.lastIndexOf("/");
    if (cut <= 0 || cut === value.length - 1 || seen.has(value)) continue;
    seen.add(value);
    out.push({ subject: value.slice(0, cut), runId: value.slice(cut + 1) });
  }
  return out;
}
