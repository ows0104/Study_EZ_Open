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

/** 족보 모아풀기 주소(2026-11-18-jokbo-mix). 족보는 시간표 칸에 붙어서 칸 ID를 고른 순서대로 싣는다. */
export const JOKBO_MIX_PATH = "/study/jokbo-mix";

export function jokboMixHref(eventIds: string[]) {
  const params = new URLSearchParams();
  for (const id of [...new Set(eventIds)]) params.append("e", id);
  return `${JOKBO_MIX_PATH}?${params.toString()}`;
}

export function readJokboMix(params: URLSearchParams): string[] {
  return [...new Set(params.getAll("e").filter(id => /^[A-Za-z0-9_-]{1,64}$/.test(id)))];
}
