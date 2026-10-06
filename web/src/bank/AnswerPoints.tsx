import { Fragment } from "react";

type Range = { start: number; end: number };

/** Keep answer offsets while allowing point shorthand such as 극성/수용성. */
const separator = /[\s·•/,;:→⇒↔=()]/;
const normalize = (text: string) => text.replace(/\*\*/g, "").split("").filter((ch) => !separator.test(ch)).join("").toLowerCase();
const filler = new Set(["더", "및", "또는", "그리고", "것", "이다", "한다", "하는", "되는", "the", "a", "an", "and", "or", "is", "are", "to", "of"]);
// These are wording equivalents, not new scoring criteria. Keep the answer itself intact.
const wording: Record<string, string[]> = {
  용이: ["하기쉽게", "쉽게", "하기쉽다", "쉽다", "쉬운"],
  불가: ["하지못", "할수없", "불가능"],
  증가: ["높인다", "높아진다", "늘린다", "늘어난다"],
  감소: ["줄인다", "줄어든다", "낮춘다", "낮아진다"],
};

function variants(point: string): string[] {
  let result = [point];
  for (const [term, equivalents] of Object.entries(wording)) {
    if (point.includes(term)) result = result.flatMap((value) => [value, ...equivalents.map((other) => value.replace(term, other))]);
  }
  return result;
}

export function answerPoints(text: string, units: string[]) {
  const bold: Range[] = [];
  let visible = "";
  for (const part of text.split(/(\*\*[^*]+\*\*)/g)) {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      bold.push({ start: visible.length, end: visible.length + part.length - 4 });
      visible += part.slice(2, -2);
    } else visible += part;
  }

  // Map normalized offsets back to the answer, including spaces inside a point.
  let normalized = "";
  const offsets: number[] = [];
  for (let i = 0; i < visible.length; i++) {
    if (separator.test(visible[i])) continue;
    const char = visible[i].toLowerCase();
    normalized += char;
    for (let j = 0; j < char.length; j++) offsets.push(i);
  }
  const highlights: Range[] = [];
  const remaining: string[] = [];
  function match(value: string): boolean {
    let found = false;
    for (const point of variants(normalize(value))) {
      if (!point) continue;
      let from = 0;
      let start: number;
      while ((start = normalized.indexOf(point, from)) !== -1) {
        const before = visible[offsets[start] - 1]?.toLowerCase() ?? "";
        const after = visible[offsets[start + point.length - 1] + 1]?.toLowerCase() ?? "";
        const insideWord = (/[a-z0-9]/.test(point[0]) && /[a-z0-9]/.test(before))
          || (/[a-z0-9]/.test(point.at(-1)!) && /[a-z0-9]/.test(after));
        if (!insideWord) {
          highlights.push({ start: offsets[start], end: offsets[start + point.length - 1] + 1 });
          found = true;
        }
        from = start + point.length;
      }
    }
    return found;
  }
  for (const unit of units) {
    const plain = unit.replace(/\*\*/g, "").trim();
    if (!plain || match(plain)) continue;
    const fragments = plain.split(/[→⇒↔=/,;:·•()]+/).filter((part) => part.trim());
    const covered = fragments.map((fragment) => {
      if (match(fragment)) return true;
      const terms = fragment.split(/\s+/).filter((term) => term.length >= 2 && !filler.has(term.toLowerCase()));
      return terms.length > 0 && terms.map(match).every(Boolean);
    }).every(Boolean);
    if (!covered && !remaining.includes(unit)) remaining.push(unit);
  }
  // Join touching keyword spans (including punctuation between 극성 and 수용성).
  const merged: Range[] = [];
  for (const range of highlights.sort((a, b) => a.start - b.start)) {
    const last = merged.at(-1);
    if (last && (range.start <= last.end || [...visible.slice(last.end, range.start)].every((ch) => separator.test(ch)))) {
      last.end = Math.max(last.end, range.end);
    } else merged.push({ ...range });
  }
  return { text: visible, bold, highlights: merged, remaining };
}

export function AnswerPoints({ text, units = [] }: { text: string; units?: string[] }) {
  const parsed = answerPoints(text, units);
  const cuts = [...new Set([0, parsed.text.length,
    ...parsed.bold.flatMap((range) => [range.start, range.end]),
    ...parsed.highlights.flatMap((range) => [range.start, range.end]),
  ])].sort((a, b) => a - b);
  return <>{cuts.slice(0, -1).map((start, i) => {
    const end = cuts[i + 1];
    const value = parsed.text.slice(start, end);
    const contains = (range: Range) => range.start <= start && range.end >= end;
    if (parsed.highlights.some(contains)) return <strong key={start} className="bank-answer-point">{value}</strong>;
    if (parsed.bold.some(contains)) return <strong key={start}>{value}</strong>;
    return <Fragment key={start}>{value}</Fragment>;
  })}</>;
}
