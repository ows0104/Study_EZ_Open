import { Fragment } from "react";
import { Stem } from "../lecture/Stem";
import { textLayout } from "./textLayout";
import { stemText } from "./stemText";

/** Only add layout: stored wording, blank order and answer units stay intact. */
export function stemLines(text: string, list = false) {
  text = stemText(text);
  const normalized = (list ? text.replace(/[ \t]*;[ \t]*/g, "\n") : text).replace(/\r\n?/g, "\n");
  // Korean sentences and cloze endings leave C. difficile, e.g. and 0.5 intact.
  const sentences = normalized.split(/(?<=[가-힣}\]][.!?])[ \t]+/);
  const labeled = (line: string) => /^(?:\*\*)?[^:：\n]{1,32}[:：]/.test(line.trim());
  const comparison = sentences.filter(labeled).length >= 2;
  // Explicit line breaks take precedence over automatic formatting.
  const lines = normalized.includes("\n") ? normalized.split(/\n+/)
    : !textLayout(normalized).list && (comparison || normalized.length >= 140) ? sentences : [normalized];
  return lines.filter(line => line.trim()).map(line => ({
    ...textLayout(line),
    text: line.trim(),
  }));
}

export function BankStem({ text, cloze = false, answerUnits, list = false }: {
  text: string; cloze?: boolean; answerUnits?: string[]; list?: boolean;
}) {
  let blank = 0;
  return <p className="quiz-stem bank-stem">
    {stemLines(text, list).map((line, index) => <Fragment key={index}>
      {index > 0 ? "\n" : null}
      <span style={line.style} className={`bank-stem-line${line.list ? " is-list" : ""}`}>
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
