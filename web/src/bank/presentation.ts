import type { BankQuestion } from "../types/bank";

/** Stable within one exposure; independently salted for each matching column. */
export function shuffled<T>(items: T[], seed: string, avoidOriginal = true): T[] {
  let h = 2166136261;
  for (const ch of seed) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    h = Math.imul(h ^ (h >>> 15), 2246822507) >>> 0;
    const j = h % (i + 1);
    [out[i], out[j]] = [out[j], out[i]];
  }
  if (avoidOriginal && out.length > 1 && out.every((x, i) => x === items[i])) out.push(out.shift() as T);
  return out;
}

export const presentationSeed = (q: BankQuestion) => q.presentationSeed ?? q.question_id;
export function matchingLayout(q: BankQuestion) {
  const seed = presentationSeed(q);
  return { left: q.matchingOrdered ? [...q.matching_left] : shuffled(q.matching_left, `${seed}:left`, false),
    right: shuffled(q.matching_right, `${seed}:right`, false) };
}
