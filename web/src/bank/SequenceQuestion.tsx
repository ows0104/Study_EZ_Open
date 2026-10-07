import type { BankAnswer, BankQuestion } from "../types/bank";
import { Stem } from "../lecture/Stem";
import { shuffled } from "./BankQuestion";
import "../styles/sequence.css";

export function sequenceComplete(q: BankQuestion, order: string[]) {
  return q.sequence_items.length > 0 && order.length === q.sequence_items.length
    && new Set(order).size === order.length && order.every(item => q.sequence_items.includes(item));
}

export function sequenceScore(q: BankQuestion, answer: BankAnswer | null, order: string[]) {
  if (q.format !== "sequence" || !answer || !sequenceComplete(q, order)
    || !sequenceComplete(q, answer.correctOrder)) return null;
  const correct = order.filter((item, index) => item === answer.correctOrder[index]).length;
  return { correct, total: order.length, rating: correct === order.length ? "Good" as const : "Again" as const };
}

export function SequenceQuestion({ question: q, answer, order, disabled, onSelect, onRemove, onReset }: {
  question: BankQuestion;
  answer: BankAnswer | null;
  order: string[];
  disabled: boolean;
  onSelect: (item: string) => void;
  onRemove: (index: number) => void;
  onReset: () => void;
}) {
  const locked = disabled || Boolean(answer);
  const score = sequenceScore(q, answer, order);
  return <div className="bank-sequence">
    <p className="bank-note">
      {answer ? "선택한 순서와 정답을 확인하세요." : "항목을 순서대로 누르면 아래에 쌓입니다. 선택한 항목을 다시 누르면 취소할 수 있습니다."}
    </p>
    <ul className="bank-sequence-options" aria-label="순서형 보기">
      {shuffled(q.sequence_items, q.question_id).map(item => {
        const selected = order.includes(item);
        return <li key={item}>
          <button type="button" className={`bank-sequence-choice${selected ? " is-picked" : ""}`}
            disabled={locked || selected} aria-pressed={selected} onClick={() => onSelect(item)}>
            <Stem text={item} />
            {selected ? <span className="bank-sequence-position">{order.indexOf(item) + 1}번 선택</span> : null}
          </button>
        </li>;
      })}
    </ul>
    <section className="bank-sequence-selection" aria-label="선택한 순서">
      <p className="bank-sequence-heading">선택한 순서 · {order.length} / {q.sequence_items.length}</p>
      {order.length ? <>
        <ol className="bank-sequence-order" aria-label="선택 순서 목록" aria-live="polite">
          {order.map((item, index) => {
            const result = score ? item === answer!.correctOrder[index] ? "is-correct" : "is-wrong" : "";
            return <li key={item}>
              <button type="button" className={`bank-sequence-choice ${result}`} disabled={locked}
                aria-label={`${index + 1}번 ${item}${answer ? "" : ", 선택 취소"}`} onClick={() => onRemove(index)}>
                <b>{index + 1}</b><span><Stem text={item} /></span>
                <span className="bank-sequence-position">{score ? result === "is-correct" ? "✓" : "✕" : answer ? "" : "× 취소"}</span>
              </button>
            </li>;
          })}
        </ol>
        {!answer ? <button type="button" className="is-quiet bank-sequence-reset" disabled={disabled} onClick={onReset}>다시 선택</button> : null}
      </> : <p className="bank-note">위에서 첫 번째 항목을 선택하세요.</p>}
    </section>
    {score ? <p className={`bank-sequence-score ${score.rating === "Good" ? "is-correct" : "is-wrong"}`} role="status">
      {score.rating === "Good" ? "순서가 모두 맞았어요!" : `순서가 달라요. ${score.correct} / ${score.total}개 위치가 맞습니다.`}
      <span className="bank-note">다음 문제로 넘어가면 {score.rating}으로 자동 기록됩니다.</span>
    </p> : null}
  </div>;
}
