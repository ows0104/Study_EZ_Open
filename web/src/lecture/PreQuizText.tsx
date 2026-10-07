import { Stem } from "./Stem";

/** Keep stored wording intact; remove the redundant label and give sentences room. */
export function formatPreQuizText(text: string): string {
  return text
    .replace(/(?:\*\*)?[\[［]\s*선택\s*도전\s*[\]］](?:\*\*)?\s*[:：]?\s*/g, "")
    .replace(/^\s*(?:\*\*)?선택\s*도전(?:\*\*)?\s*[:：]\s*(?:\*\*)?\s*/, "")
    .replace(/\r\n?/g, "\n")
    // Korean sentence endings only: decimals, English abbreviations and drug
    // names containing punctuation stay intact. Existing newlines are preserved.
    .replace(/([가-힣][.!?])[^\S\n]+/g, "$1\n\n")
    .trim();
}

export function PreQuizText({ text }: { text: string }) {
  return <span className="prequiz-text">
    {formatPreQuizText(text).split(/\n{2,}/).map((paragraph, index) => (
      <span className="prequiz-text-paragraph" key={index}><Stem text={paragraph} /></span>
    ))}
  </span>;
}
