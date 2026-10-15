import { Stem } from "../lecture/Stem";
import type { BankAnswer, BankQuestion } from "../types/bank";
import { SlideImage } from "../SlideImage";
import type { SlidePreloader } from "../slidePreload";
import { AnswerPoints, answerPoints } from "./AnswerPoints";

/**
 * 문항 ID 를 씨로 삼아 섞는다 — 다시 불러도, 답을 펴도 같은 순서다. 섞은 결과가 원래와 같으면 한 칸 민다.
 *
 * 짝짓기 오른쪽 목록을 위한 것이다. 261002_03 의 짝짓기 5문항 중 4문항이 오른쪽을 정답 순서 그대로 냈다
 * (2026-10-05) — 줄만 맞춰 읽으면 답이 된다.
 */
export function shuffled<T>(items: T[], seed: string): T[] {
  let h = 2166136261;
  for (const ch of seed) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    h = Math.imul(h ^ (h >>> 15), 2246822507) >>> 0;
    const j = h % (i + 1);
    [out[i], out[j]] = [out[j], out[i]];
  }
  if (out.length > 1 && out.every((x, i) => x === items[i])) out.push(out.shift() as T);
  return out;
}

const letter = (index: number) => String.fromCharCode(65 + index);

/** ChatGPT 가 항목에 스스로 붙인 꼬리표(`L1:` · `R2:`). 화면의 1·2·A·B 와 겹치므로 보일 때만 뗀다 — 짝은 원문으로 맞춘다. */
const bare = (item: string) => item.replace(/^[LR]\d+\s*[:.)]\s*/, "");

export function choiceScore(q: BankQuestion, answer: BankAnswer | null, picked: Set<string>) {
  if (!answer || answer.personalAnswer || !["mcq", "multi_select"].includes(q.format)) return null;
  const options = new Set(q.options.map(option => option.id));
  const expected = new Set(answer.correctOptionIds);
  if (!expected.size || [...expected, ...picked].some(id => !options.has(id))) return null;
  const correct = [...picked].filter(id => expected.has(id)).length;
  const missed = expected.size - correct;
  const wrong = picked.size - correct;
  return { correct, missed, wrong, allCorrect: missed === 0 && wrong === 0 };
}

/** 발문. cloze 빈칸은 답을 보면 채운다. */
export function QuestionBody({ question: q, answer, picked, onPick, matching, sequence, showOptions = true, disabled = false }: {
  question: BankQuestion;
  answer: BankAnswer | null;
  picked: Set<string>;
  onPick: (id: string) => void;
  matching?: import("react").ReactNode;
  sequence?: import("react").ReactNode;
  showOptions?: boolean;
  disabled?: boolean;
}) {
  const score = choiceScore(q, answer, picked);
  const parts = q.format === "cloze" ? q.question.split(/(\{\{c\d+\}\})/g) : [q.question];
  let blank = 0;
  return (
    <>
      <p className="quiz-stem">
        {parts.map((part, index) => {
          if (!/^\{\{c\d+\}\}$/.test(part)) return <Stem key={index} text={part} />;
          const unit = answer?.answerUnits[blank];
          blank += 1;
          if (unit !== undefined) return <strong key={index} className="bank-answer-point"><Stem text={unit} /></strong>;
          return (
            <span key={index} className="bank-blank">
              {`[ ${blank} ]`}
            </span>
          );
        })}
      </p>
      {q.format === "ox" && !answer ? <p className="bank-note">O 인가 X 인가, 그리고 왜인가</p> : null}
      {q.mcq_mode === "recall_first" && !showOptions ? <p className="bank-note">기억 확인형 · 먼저 답을 떠올린 뒤 선지를 공개하세요.</p> : null}
      {q.options.length && showOptions ? (
        <ul className="bank-options">
          {q.options.map((option) => {
            const selected = picked.has(option.id);
            const correct = answer?.correctOptionIds.includes(option.id);
            const result = score ? correct ? selected ? "is-correct" : "is-missed" : selected ? "is-wrong" : "" : "";
            const label = score ? correct ? selected ? "✓ 맞게 고른 정답" : "! 빠뜨린 정답 · 미선택"
              : selected ? "✕ 잘못 고른 선지" : "정답 아님 · 미선택" : "";
            const cls = `${selected ? " is-picked" : ""}${result ? ` ${result}` : ""}`;
            return (
              <li key={option.id}>
                <button type="button" className={`bank-option${cls}`} disabled={disabled || Boolean(answer)}
                  aria-pressed={selected} onClick={() => onPick(option.id)}>
                  <b>{option.id}</b> {option.text}
                  {label ? <span className="bank-option-result">{label}</span> : null}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
      {showOptions && score ? <p className={`bank-choice-score ${score.allCorrect ? "is-correct" : "is-wrong"}`} role="status">
        <strong>{score.allCorrect ? "모두 맞았어요!" : picked.size ? "정답과 선택이 달라요." : "선택한 답이 없어요."}</strong>
        <span>맞게 고른 정답 {score.correct}개 · 빠뜨린 정답 {score.missed}개 · 잘못 고른 선지 {score.wrong}개</span>
        <span className="bank-note">아래에서 Again·Hard·Good·Easy 중 체감 난이도에 맞는 평가를 고르세요.</span>
      </p> : null}
      {q.format === "matching" ? (
        matching ?? (
        <div className="bank-match">
          <ul>{q.matching_left.map((item, index) => <li key={item}><b>{index + 1}</b> {bare(item)}</li>)}</ul>
          <ul>
            {shuffled(q.matching_right, q.question_id).map((item, index) => (
              <li key={item}><b>{letter(index)}</b> {bare(item)}</li>
            ))}
          </ul>
        </div>
        )
      ) : null}
      {q.format === "sequence" ? (
        sequence ?? <ul className="bank-items">{q.sequence_items.map((item) => <li key={item}>{item}</li>)}</ul>
      ) : null}
    </>
  );
}

export function AnswerBody({ question: q, answer, preload }: {
  question: BankQuestion; answer: BankAnswer; preload?: SlidePreloader;
}) {
  const review = answer.medicalReview;
  const right = q.format === "matching" ? shuffled(q.matching_right, q.question_id) : [];
  const remainingPoints = answerPoints(answer.answer, answer.answerUnits).remaining;
  const shortUnits = q.format === "basic"
    ? answer.answerUnits.filter((unit) => unit.replace(/\*\*/g, "").trim()) : [];
  const conciseAnswer = shortUnits.length > 0;
  const shortExplanation = conciseAnswer && answer.answer.trim().length > 0
    && answerPoints(answer.answer, []).text.trim() !== shortUnits.map((unit) => answerPoints(unit, []).text.trim()).join("\n");
  const choice = ["mcq", "multi_select"].includes(q.format) && !answer.personalAnswer;
  const choiceUnits = new Map<string, string[]>();
  const linkedUnits = new Set<string>();
  if (choice) for (const unit of answer.answerUnits) {
    const match = unit.match(/^\s*(\*\*)?([^:：.)\s*]+)(?:\*\*)?\s*[:：.)]\s*(.+)$/s);
    const id = match?.[2];
    if (!id || !q.options.some(option => option.id === id)) continue;
    const text = (match![1] ? match![3].replace(/^\*\*\s*/, "") : match![3]).trim();
    if (!text) continue;
    choiceUnits.set(id, [...(choiceUnits.get(id) ?? []), text]);
    linkedUnits.add(unit);
  }
  const extraChoiceUnits = remainingPoints.filter(unit => !linkedUnits.has(unit));
  return (
    <>
      {/* 단답은 모든 tier에서 채점 항목 자체가 답이다. 부연설명은 필요할 때만 펼친다. */}
      {conciseAnswer ? (
        <>
          <ul className="quiz-answer bank-short-answer">
            {shortUnits.map((unit, index) => <li key={index}><AnswerPoints text={unit} units={[unit]} /></li>)}
          </ul>
          {shortExplanation ? (
            <details className="bank-answer-context">
              <summary>설명 보기</summary>
              <p><Stem text={answer.answer} /></p>
            </details>
          ) : null}
        </>
      ) : null}
      {/* Cloze는 위 발문에 정답을 채워 보여 준다. 짝짓기는 아래 짝이 곧 답이다. */}
      {conciseAnswer || (q.format === "cloze" && !answer.personalAnswer) || (q.format === "matching" && answer.answerPairs.length) ? null : (
        <p className="quiz-answer">
          <AnswerPoints text={answer.answer} units={answer.answerUnits} />
        </p>
      )}
      {answer.explanation?.trim() && !answer.personalAnswer ? (
        <section className="quiz-explanation bank-explanation" aria-label="해설">
          <h2>해설</h2>
          <p><Stem text={answer.explanation} /></p>
        </section>
      ) : null}
      {/* 이전 O/X 은행의 채점 단위에 저장된 근거도 계속 보여 준다. */}
      {q.format === "ox" && !answer.personalAnswer && !answer.explanation?.trim() ? (
        <section className="quiz-explanation bank-ox-explanation" aria-label="해설">
          <h2>해설</h2>
          {answer.answerUnits.some((unit) => unit.trim() && !/^[OX]$/i.test(unit.trim())) ? (
            <ul>{answer.answerUnits.filter((unit) => unit.trim() && !/^[OX]$/i.test(unit.trim())).map((unit, index) => (
              <li key={index} className="bank-answer-point"><Stem text={unit} /></li>
            ))}</ul>
          ) : <p>이 문항에 등록된 해설이 없습니다.</p>}
        </section>
      ) : null}
      {choice ? (
        <section className="quiz-explanation bank-choice-explanation" aria-label="선지별 해설">
          <h2>선지별 해설</h2>
          <ul>
            {q.options.map(option => (
              <li key={option.id}>
                <p><b>{option.id}</b> <Stem text={option.text} />
                  <span className="bank-note"> · {answer.correctOptionIds.includes(option.id) ? "정답 선지" : "정답이 아닌 선지"}</span>
                </p>
                {choiceUnits.has(option.id) ? choiceUnits.get(option.id)!.map((text, index) => (
                  <p key={index}><Stem text={text} /></p>
                )) : <p className="bank-note">이 선지에 등록된 해설이 없습니다.</p>}
              </li>
            ))}
            {extraChoiceUnits.map(unit => <li key={unit}><Stem text={unit} /></li>)}
          </ul>
        </section>
      ) : null}
      {/* 답에서 강조한 포인트는 반복하지 않는다. 답과 표현이 다른 설명은 보존한다. */}
      {!conciseAnswer && !choice && remainingPoints.length > 0 && !["ox", "cloze", "matching", "sequence"].includes(q.format) ? (
        <ul className="bank-units">{remainingPoints.map((unit) => <li key={unit}><Stem text={unit} /></li>)}</ul>
      ) : null}
      {answer.answerPairs.length ? (
        <ul className="bank-units">
          {answer.answerPairs.map((pair) => (
            <li key={`${pair.left}-${pair.right}`} className="bank-answer-point">
              {bare(pair.left)} → {right.includes(pair.right) ? <b>{letter(right.indexOf(pair.right))}</b> : null}{" "}
              {bare(pair.right)}
            </li>
          ))}
        </ul>
      ) : null}
      {answer.correctOrder.length ? (
        <section className="bank-correct-order" aria-label="정답 순서">
          <p className="bank-note">정답 순서</p>
          <ol className="bank-order bank-answer-point">
            {answer.correctOrder.map(item => <li key={item}><Stem text={item} /></li>)}
          </ol>
        </section>
      ) : null}
      {answer.conflict ? (
        <p className="bank-conflict">
          <b>자료 충돌</b> {answer.conflict}
        </p>
      ) : null}
      {answer.external ? (
        <p className="bank-note">이 문항에는 강의자료·족보에 없는 내용(외부 의학지식)이 들어 있습니다.</p>
      ) : null}
      {answer.reviewIssues?.map((issue, index) => <p className="bank-review is-doubt" key={index}><b>문항 검수 · 미해결</b> {issue}</p>)}
      {review && review.verdict !== "ok" ? (
        <p className={`bank-review is-${review.verdict}`}>
          <b>외부지식 검토 · {review.verdict === "wrong" ? "틀림" : "의심"}</b> {review.note}
          {review.suggested_answer ? <><br />맞는 답: {review.suggested_answer}</> : null}
        </p>
      ) : null}
      {answer.slides.map((slide) => (
        <SlideImage key={slide.page} preload={preload} src={slide.url} alt={`필기 ${slide.page}쪽`} />
      ))}
    </>
  );
}
