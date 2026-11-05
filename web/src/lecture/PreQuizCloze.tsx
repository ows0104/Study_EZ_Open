import { Fragment, type ReactNode } from "react";
import type { ClozePart } from "../types/quiz";
import { formatPreQuizText, PreQuizText } from "./PreQuizText";

/** Parts come only from a revealed answer. Without them, keep the original front. */
export function PreQuizCloze({ text, parts }: { text: string; parts?: ClozePart[] }) {
  if (!parts?.some((part) => part.blank)) return <PreQuizText text={text} />;

  // Use collision-free markers so formatting and bold spans can cross blank boundaries.
  let marker = "\uE000";
  const wording = parts.map((part) => part.text).join("");
  while (wording.includes(marker)) marker += "\uE000";
  const open = `${marker}a`;
  const close = `${marker}z`;
  const marked = parts.map((part) => part.blank ? `${open}${part.text}${close}` : part.text).join("");
  let inBlank = false;
  function inline(value: string): ReactNode[] {
    return value.split(new RegExp(`(${open}|${close})`, "g")).map((part, index) => {
      if (part === open) { inBlank = true; return null; }
      if (part === close) { inBlank = false; return null; }
      return inBlank ? <strong key={index} className="bank-answer-point">{part}</strong> : <Fragment key={index}>{part}</Fragment>;
    });
  }
  return <span className="prequiz-text">
    {formatPreQuizText(marked).split(/\n{2,}/).map((paragraph, index) => (
      <span className="prequiz-text-paragraph" key={index}>
        {paragraph.split(/(\*\*[^*]+\*\*)/g).map((part, partIndex) =>
          part.startsWith("**") && part.endsWith("**") && part.length > 4
            ? <strong key={partIndex}>{inline(part.slice(2, -2))}</strong>
            : <Fragment key={partIndex}>{inline(part)}</Fragment>)}
      </span>
    ))}
  </span>;
}
