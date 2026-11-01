import type { BankFullQuestion } from "../types/bank";

/** Answers belong in the editor only; served questions keep answer-free markers. */
export function clozeDraft(text: string, units: string[]): string {
  let index = 0;
  return text.replace(/\{\{c\d+\}\}/g, marker => {
    const answer = units[index++];
    return answer === undefined ? marker : `{${answer}}`;
  });
}

export function clozeAnswer(text: string) {
  const units: string[] = [];
  const question = text.replace(/(?<!\{)\{([^{}\r\n]+)\}(?!\})/g, (_, answer: string) => {
    units.push(answer.trim());
    return "{{c1}}";
  });
  let index = 0;
  const answer = question.replace(/\{\{c\d+\}\}/g, marker => units[index++] ?? marker);
  return { question, answer, answer_units: units };
}

export function editorQuestion(q: BankFullQuestion): BankFullQuestion {
  if (q.format === "ox" && !q.explanation?.trim()) {
    const reasons = q.answer_units.filter(unit => unit.trim() && !/^[OX]$/i.test(unit.trim()));
    return { ...q, explanation: reasons.join("\n") };
  }
  return q.format === "cloze" ? { ...q, question: clozeDraft(q.question, q.answer_units) } : { ...q };
}

export function saveQuestion(q: BankFullQuestion): BankFullQuestion {
  if (q.format === "cloze") return { ...q, ...clozeAnswer(q.question) };
  if (q.format === "basic" || q.format === "list" || q.format === "ox") {
    return { ...q, answer_units: q.format === "ox" ? [q.answer.trim()]
      : q.format === "basic" ? [q.answer.trim()] : q.answer.split(/\r?\n/).map(s => s.trim()).filter(Boolean) };
  }
  if (q.format === "matching") {
    const units = q.answer_pairs.map(p => `${p.left} - ${p.right}`);
    return { ...q, answer: units.join("\n"), answer_units: units };
  }
  if (q.format === "sequence") return { ...q, answer: q.correct_order.join(" → "), answer_units: [...q.correct_order] };
  const correct = q.options.filter(o => q.correct_option_ids.includes(o.id));
  return { ...q, answer: correct.map(o => `${o.id}. ${o.text}`).join("\n") };
}
