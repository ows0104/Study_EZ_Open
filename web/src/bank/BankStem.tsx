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

export function BankStem({ text, cloze = false, answerUnits, list = false, blankOffset = 0 }: {
  text: string; cloze?: boolean; answerUnits?: string[]; list?: boolean; blankOffset?: number;
}) {
  let blank = blankOffset;
  const inline = (value: string) => (cloze ? value.split(/(\{\{c\d+\}\})/g) : [value]).map((part, partIndex) => {
    if (!cloze || !/^\{\{c\d+\}\}$/.test(part)) return <Stem key={partIndex} text={part} />;
    const unit = answerUnits?.[blank]; blank += 1;
    return unit !== undefined
      ? <strong key={partIndex} className="bank-answer-point"><Stem text={unit} /></strong>
      : <span key={partIndex} className="bank-blank">{`[ ${blank} ]`}</span>;
  });
  const rows = stemText(text).replace(/\r\n?/g, "\n").split("\n");
  const cells = (row: string) => row.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map(cell => cell.trim().replace(/\\\|/g, "|"));
  const tableAt = rows.findIndex((row, i) => row.trim().startsWith("|") && rows[i + 1]?.trim().startsWith("|")
    && cells(rows[i + 1]).every(cell => /^:?-{3,}:?$/.test(cell)));
  if (tableAt >= 0) {
    const header = cells(rows[tableAt]); let end = tableAt + 2;
    while (end < rows.length && rows[end].trim().startsWith("|") && cells(rows[end]).length === header.length) end += 1;
    const body = rows.slice(tableAt + 2, end).map(cells);
    // A valid, rectangular table only. Other text keeps the existing rendering.
    if (header.length > 1 && cells(rows[tableAt + 1]).length === header.length && body.length) return <div className="quiz-stem bank-stem">
      {rows.slice(0, tableAt).map((row, i) => <div key={`before-${i}`}>{inline(row)}</div>)}
      <div style={{ overflowX: "auto", margin: "16px 0" }}><table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead><tr>{header.map((cell, i) => <th scope="col" key={i} style={{ border: "1px solid #cbd5e1", padding: "10px", textAlign: "left" }}>{inline(cell)}</th>)}</tr></thead>
        <tbody>{body.map((row, i) => <tr key={i}>{row.map((cell, j) => j === 0
          ? <th scope="row" key={j} style={{ border: "1px solid #cbd5e1", padding: "10px", textAlign: "left", fontWeight: 500 }}>{inline(cell)}</th>
          : <td key={j} style={{ border: "1px solid #cbd5e1", padding: "10px" }}>{inline(cell)}</td>)}</tr>)}</tbody>
      </table></div>
      {end < rows.length ? <BankStem text={rows.slice(end).join("\n")} cloze={cloze} answerUnits={answerUnits} blankOffset={blank} list={list} /> : null}
    </div>;
  }
  return <p className="quiz-stem bank-stem">
    {stemLines(text, list).map((line, index) => <Fragment key={index}>
      {index > 0 ? "\n" : null}
      <span style={line.style} className={`bank-stem-line${line.list ? " is-list" : ""}`}>
        {inline(line.text)}
      </span>
    </Fragment>)}
  </p>;
}
