import { Fragment } from "react";

type Range = { start: number; end: number };

/** Compare visible text, keeping the original spelling and spacing for display. */
const normalize = (text: string) => text.replace(/\*\*/g, "").replace(/\s+/g, "").toLowerCase();

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
    if (/\s/.test(visible[i])) continue;
    const char = visible[i].toLowerCase();
    normalized += char;
    for (let j = 0; j < char.length; j++) offsets.push(i);
  }
  const highlights: Range[] = [...bold];
  const remaining: string[] = [];
  for (const unit of units) {
    const point = normalize(unit);
    if (!point) continue;
    let from = 0;
    let found = false;
    let start: number;
    while ((start = normalized.indexOf(point, from)) !== -1) {
      // A short English point must not color a fragment of another word.
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
    // Some banks paraphrase the grading point, and O/X explanations live only in units.
    if (!found && !remaining.includes(unit)) remaining.push(unit);
  }
  return { text: visible, bold, highlights, remaining };
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
    return <Fragment key={start}>{value}</Fragment>;
  })}</>;
}
