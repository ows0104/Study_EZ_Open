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

/** 발문. cloze 빈칸은 답을 보면 채운다. */
export function QuestionBody({ question: q, answer, picked, onPick, matching, sequence }: {
  question: BankQuestion;
  answer: BankAnswer | null;
  picked: Set<string>;
  onPick: (id: string) => void;
  matching?: import("react").ReactNode;
  sequence?: import("react").ReactNode;
}) {
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
      {q.options.length ? (
        <ul className="bank-options">
          {q.options.map((option) => {
            const correct = answer?.correctOptionIds.includes(option.id);
            const cls = `${picked.has(option.id) ? " is-picked" : ""}${correct ? " is-correct" : ""}`;
            return (
              <li key={option.id}>
                <button className={`bank-option${cls}`} disabled={Boolean(answer)} onClick={() => onPick(option.id)}>
                  <b>{option.id}</b> {option.text}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
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
      {conciseAnswer || q.format === "cloze" || (q.format === "matching" && answer.answerPairs.length) ? null : (
        <p className="quiz-answer">
          <AnswerPoints text={answer.answer} units={answer.answerUnits} />
        </p>
      )}
      {/* O/X의 채점 단위는 판단의 이유다. 한 항목이어도 해설 전체를 보여 준다. */}
      {q.format === "ox" ? (
        <section className="quiz-explanation bank-ox-explanation" aria-label="해설">
          <h2>해설</h2>
          {answer.answerUnits.some((unit) => unit.trim()) ? (
            <ul>{answer.answerUnits.filter((unit) => unit.trim()).map((unit, index) => (
              <li key={index} className="bank-answer-point"><Stem text={unit} /></li>
            ))}</ul>
          ) : <p>이 문항에 등록된 해설이 없습니다.</p>}
        </section>
      ) : null}
      {/* 답에서 강조한 포인트는 반복하지 않는다. 답과 표현이 다른 설명은 보존한다. */}
      {!conciseAnswer && remainingPoints.length > 0 && !["ox", "cloze", "matching", "sequence"].includes(q.format) ? (
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
