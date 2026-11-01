import { Stem } from "../lecture/Stem";
import type { BankAnswer, BankQuestion } from "../types/bank";
import { matchingLayout } from "./presentation";
import "../styles/matching.css";

export type MatchingPicks = Record<string, string>;
export const MATCHING_UNKNOWN = "\u0000unknown";
const letter = (index: number) => String.fromCharCode(65 + index);
const bare = (item: string) => item.replace(/^[LR]\d+\s*[:.)]\s*/, "");

export function matchingScore(q: BankQuestion, answer: BankAnswer | null, picks: MatchingPicks) {
  if (!answer || q.format !== "matching" || !q.matching_left.length) return null;
  const expected = new Map(answer.answerPairs.map(pair => [pair.left, pair.right]));
  if (!q.matching_left.every(left => q.matching_right.includes(expected.get(left) ?? ""))) return null;
  const correct = q.matching_left.filter(left => picks[left] === expected.get(left)).length;
  return { correct, total: q.matching_left.length, allCorrect: correct === q.matching_left.length };
}

export function MatchingQuestion({ question: q, answer, picks, active, disabled, onActive, onMatch }: {
  question: BankQuestion;
  answer: BankAnswer | null;
  picks: MatchingPicks;
  active: number;
  disabled: boolean;
  onActive: (index: number) => void;
  onMatch: (right: string) => void;
}) {
  const { left: leftItems, right } = matchingLayout(q);
  const score = matchingScore(q, answer, picks);
  const expected = new Map(answer?.answerPairs.map(pair => [pair.left, pair.right]));
  return <>
    <p className="bank-note">
      {answer ? "선택한 짝과 정답을 확인하세요." : "오른쪽 항목을 누르면 1번부터 연결됩니다. 모르는 항목은 ‘모르겠음’을 고르거나 비워 둔 채 채점할 수 있습니다. 수정할 번호를 왼쪽에서 선택하세요."}
    </p>
    <div className="bank-match">
      <ul aria-label="짝짓기 번호">
        {leftItems.map((left, index) => {
          const selected = right.indexOf(picks[left]);
          const pickedLabel = picks[left] === MATCHING_UNKNOWN ? "모르겠음" : selected >= 0 ? letter(selected) : "—";
          const result = score ? picks[left] === expected.get(left) ? "is-correct" : "is-wrong" : "";
          return <li key={left}>
            <button type="button" className={`bank-match-choice ${!answer && active === index ? "is-active" : ""} ${result}`}
              disabled={disabled || Boolean(answer)} aria-pressed={!answer && active === index}
              aria-label={`${index + 1}번 ${bare(left)}, 선택 ${pickedLabel === "—" ? "없음" : pickedLabel}`}
              onClick={() => onActive(index)}>
              <b>{index + 1}</b>
              <span className="bank-match-picked">{pickedLabel}</span>
              <span><Stem text={bare(left)} /></span>
              {score ? <span className="bank-match-result">{result === "is-correct" ? "✓" : `✕ 정답 ${letter(right.indexOf(expected.get(left)!))}`}</span> : null}
            </button>
          </li>;
        })}
      </ul>
      <ul aria-label="짝짓기 보기">
        {right.map((item, index) => <li key={item}>
          <button type="button" className={`bank-match-choice ${picks[leftItems[active]] === item ? "is-picked" : ""}`}
            disabled={disabled || Boolean(answer)} aria-pressed={picks[leftItems[active]] === item}
            onClick={() => onMatch(item)}>
            <b>{letter(index)}</b> <span><Stem text={bare(item)} /></span>
          </button>
        </li>)}
        <li>
          <button type="button" className={`bank-match-choice ${picks[leftItems[active]] === MATCHING_UNKNOWN ? "is-picked" : ""}`}
            disabled={disabled || Boolean(answer)} aria-pressed={picks[leftItems[active]] === MATCHING_UNKNOWN}
            onClick={() => onMatch(MATCHING_UNKNOWN)}>모르겠음</button>
        </li>
      </ul>
    </div>
    {score ? <p className={`bank-match-score ${score.allCorrect ? "is-correct" : "is-wrong"}`} role="status">
      {score.correct} / {score.total}개 정답 · {score.allCorrect ? "모두 맞았어요!" : "틀린 짝을 확인하세요."}
      <span className="bank-note">아래에서 Again·Hard·Good·Easy 중 체감 난이도에 맞는 평가를 고르세요.</span>
    </p> : null}
  </>;
}
