import { Fragment } from "react";
import { Stem } from "../lecture/Stem";
import { textLayout } from "./textLayout";

/** Only add layout: stored wording, blank order and answer units stay intact. */
export function stemLines(text: string) {
  const normalized = text.replace(/\r\n?/g, "\n");
  // Korean sentences and cloze endings leave C. difficile, e.g. and 0.5 intact.
  const sentences = normalized.split(/(?<=[가-힣}\]][.!?])[ \t]+/);
  const labeled = (line: string) => /^(?:\*\*)?[^:：\n]{1,32}[:：]/.test(line.trim());
  const comparison = sentences.filter(labeled).length >= 2;
  // Explicit line breaks take precedence over automatic formatting.
  const lines = normalized.includes("\n") ? normalized.split(/\n+/)
    : !textLayout(normalized).list && (comparison || normalized.length >= 140) ? sentences : [normalized];
  const hasItems = comparison || lines.filter(labeled).length >= 2;
  return lines.filter(line => line.trim()).map((line, index) => ({
    ...textLayout(line),
    text: line.trim(),
    indented: index > 0 || /^[ \t]+/.test(line),
    item: labeled(line) && hasItems,
  }));
}

export function BankStem({ text, cloze = false, answerUnits }: {
  text: string; cloze?: boolean; answerUnits?: string[];
}) {
  let blank = 0;
  return <p className="quiz-stem bank-stem">
    {stemLines(text).map((line, index) => <Fragment key={index}>
      {index > 0 ? "\n" : null}
      <span style={line.style} className={`bank-stem-line${line.list ? " is-list" : line.indented ? line.item ? " is-item" : line.style ? "" : " is-sentence" : ""}`}>
        {(cloze ? line.text.split(/(\{\{c\d+\}\})/g) : [line.text]).map((part, partIndex) => {
          if (!cloze || !/^\{\{c\d+\}\}$/.test(part)) return <Stem key={partIndex} text={part} />;
          const unit = answerUnits?.[blank];
          blank += 1;
          return unit !== undefined
            ? <strong key={partIndex} className="bank-answer-point"><Stem text={unit} /></strong>
            : <span key={partIndex} className="bank-blank">{`[ ${blank} ]`}</span>;
        })}
      </span>
    </Fragment>)}
  </p>;
}
