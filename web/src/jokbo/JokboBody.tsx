import type { JokboItem } from "../types/jokbo";
import type { Verdict } from "./selection";

/**
 * 족보 문항 한 개의 본문 — 공통 지문·문제·그림·선지, 펴면 정답·선지별 해설·해설.
 * 풀이 카드, 끝 화면의 넣은 문제, 오답노트 카드가 같이 쓴다(2026-11-14).
 *
 * 읽기 쉬움이 먼저다: 폭은 바깥(`jokbo.css`)이 좁히고, 선지는 번호 뒤 글이 한 덩어리로
 * 들여 감기도록 번호와 글을 나눠 둔다.
 */
export function JokboBody({ item, picked, revealed, verdict, changed, onPick, eagerImages }: {
  item: JokboItem;
  picked: number[];
  revealed: boolean;
  /** 이번에 고른 결과. 없으면 판정 없이 정답만 보인다. */
  verdict?: Verdict | null;
  changed?: Set<number>;
  onPick?: (n: number) => void;
  eagerImages?: boolean;
}) {
  const x = item.explanation;
  const word = verdict === "correct" ? "맞음" : verdict === "wrong" ? "틀림"
    : verdict === "ungraded" || (revealed && item.answerStatus === "missing") ? "답안지에 답 없음" : null;
  const key = item.answerStatus === "all-correct" ? "전원 정답"
    : item.answerStatus === "missing" ? (x?.proposedAnswers?.length ? `추정 ${x.proposedAnswers.join(", ")}` : "")
    : `정답 ${item.answers.join(item.answerMode === "all_of" ? " + " : " 또는 ")}`;
  return (
    <>
      {item.sharedPrompt ? <p className="jokbo-shared">{item.sharedPrompt}</p> : null}
      <p className="jokbo-stem">{item.stem}</p>
      {item.figures?.length ? (
        <div className="jokbo-figures">
          {item.figures.map(f => (f.url
            ? <img key={f.file} src={f.url} alt="" width={f.w} height={f.h} loading={eagerImages ? "eager" : "lazy"} />
            : null))}
        </div>
      ) : null}
      <ul className="bank-options jokbo-options">
        {item.choices.map((choice, i) => {
          const n = i + 1;
          const selected = picked.includes(n);
          const right = item.answerStatus === "all-correct" || item.answers.includes(n);
          const cls = !revealed ? (selected ? " is-picked" : "")
            : item.answerStatus === "missing" ? (selected ? " is-picked" : "")
            : right ? (selected ? " is-correct" : " is-missed") : selected ? " is-wrong" : "";
          const note = revealed ? x?.choiceNotes?.[i] : undefined;
          return (
            <li key={n}>
              <button type="button" className={`bank-option${cls}${changed?.has(i) ? " is-changed" : ""}`}
                disabled={revealed || !onPick} aria-pressed={selected}
                aria-keyshortcuts={onPick && n <= 9 ? String(n) : undefined} onClick={() => onPick?.(n)}>
                <b>{n}</b><span>{choice}</span>
              </button>
              {note ? <p className="jokbo-choice-note">{note}</p> : null}
            </li>
          );
        })}
      </ul>

      {revealed ? (
        <div className="jokbo-answer">
          <p className={`jokbo-verdict is-${verdict ?? "none"}`}>
            {word ? <strong>{word}</strong> : null}
            {key ? <span>{key}</span> : null}
          </p>
          {item.keyConflict && item.mergedFrom ? (
            <p className="jokbo-caution">해마다 답안지 답이 다름: {item.yearLabel} {item.answers.join(",")}
              {item.mergedFrom.map(m => ` · ${m.yearLabel} ${m.answers.join(",") || "–"}`).join("")}</p>
          ) : null}
          {x?.caution ? <p className="jokbo-caution">{x.caution}</p> : null}
          {x ? <p className="jokbo-explain">{x.text}</p> : null}
          {item.correctionNote ? <p className="jokbo-correction">교정: {item.correctionNote}</p> : null}
          {x ? (
            <p className="jokbo-basis">
              {x.basis.kind === "notes" ? `필기${x.basis.pages?.length ? ` p.${x.basis.pages.join(", ")}` : ""}` : "일반 지식"}
              {" · "}{[item, ...(item.mergedFrom ?? [])].map(c => `${c.yearLabel} ${c.number}번`).join(" · ")}
            </p>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
