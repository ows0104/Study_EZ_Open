import { Stem } from "../lecture/Stem";
import type { BankAnswer, BankQuestion } from "../types/bank";
import type { SlidePreloader } from "../slidePreload";
import { AnswerPoints, answerPoints } from "./AnswerPoints";
import { BankStem } from "./BankStem";
import { BankSourceNote } from "./BankSourceNote";
import { BankSlides } from "./BankSlides";
import { BankJokboSlides } from "./BankJokboSlides";
import { BankEvidenceNotice } from "./BankEvidenceNotice";
import { matchingLayout, presentationSeed, shuffled } from "./presentation";
import "./review-notes.css";
export { shuffled } from "./presentation";

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
  return (
    <>
      <BankStem text={q.question} list={q.format === "list"} cloze={q.format === "cloze"} answerUnits={answer?.answerUnits} />
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
          <ul>{matchingLayout(q).left.map((item, index) => <li key={item}><b>{index + 1}</b> {bare(item)}</li>)}</ul>
          <ul>
            {matchingLayout(q).right.map((item, index) => (
              <li key={item}><b>{letter(index)}</b> {bare(item)}</li>
            ))}
          </ul>
        </div>
        )
      ) : null}
      {q.format === "sequence" ? (
        sequence ?? <ul className="bank-items">{shuffled(q.sequence_items, presentationSeed(q)).map((item) => <li key={item}>{item}</li>)}</ul>
      ) : null}
    </>
  );
}

export function AnswerBody({ question: q, answer, preload }: {
  question: BankQuestion; answer: BankAnswer; preload?: SlidePreloader;
}) {
  const review = answer.medicalReview;
  const hasMedicalReview = review && review.verdict !== "ok";
  const hasReviewNotes = answer.reviewIssues?.length || hasMedicalReview
    || answer.evidenceStatus || answer.conflict?.trim() || answer.external;
  const layout = q.format === "matching" ? matchingLayout(q) : { left: [], right: [] };
  const right = layout.right;
  const pairs = q.format === "matching" ? [...answer.answerPairs].sort((a, b) => layout.left.indexOf(a.left) - layout.left.indexOf(b.left)) : answer.answerPairs;
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
            {shortUnits.map((unit, index) => <li key={index}><AnswerPoints text={unit} units={[unit]} readable /></li>)}
          </ul>
          {shortExplanation ? (
            <details className="bank-answer-context">
              <summary>설명 보기</summary>
              <p><AnswerPoints text={answer.answer} readable /></p>
            </details>
          ) : null}
        </>
      ) : null}
      {/* Cloze는 위 발문에 정답을 채워 보여 준다. 짝짓기는 아래 짝이 곧 답이다. */}
      {conciseAnswer || (q.format === "cloze" && !answer.personalAnswer) || (q.format === "matching" && answer.answerPairs.length) ? null : (
        <p className="quiz-answer">
          <AnswerPoints text={answer.answer} units={q.format === "ox" ? [] : answer.answerUnits} readable list={q.format === "list"} />
        </p>
      )}
      {answer.explanation?.trim() && !answer.personalAnswer ? (
        <section className="quiz-explanation bank-explanation" aria-label="해설">
          <h2>해설</h2>
          <p><AnswerPoints text={answer.explanation} readable blueBold={q.format === "ox"} /></p>
        </section>
      ) : null}
      {/* 이전 O/X 은행의 채점 단위에 저장된 근거도 계속 보여 준다. */}
      {q.format === "ox" && !answer.personalAnswer && !answer.explanation?.trim() ? (
        <section className="quiz-explanation bank-ox-explanation" aria-label="해설">
          <h2>해설</h2>
          {answer.answerUnits.some((unit) => unit.trim() && !/^[OX]$/i.test(unit.trim())) ? (
            <ul>{answer.answerUnits.filter((unit) => unit.trim() && !/^[OX]$/i.test(unit.trim())).map((unit, index) => (
              <li key={index}><AnswerPoints text={unit} readable blueBold /></li>
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
                  <p key={index}><AnswerPoints text={text} readable /></p>
                )) : <p className="bank-note">이 선지에 등록된 해설이 없습니다.</p>}
              </li>
            ))}
            {extraChoiceUnits.map(unit => <li key={unit}><AnswerPoints text={unit} readable /></li>)}
          </ul>
        </section>
      ) : null}
      {/* 답에서 강조한 포인트는 반복하지 않는다. 답과 표현이 다른 설명은 보존한다. */}
      {!conciseAnswer && !choice && remainingPoints.length > 0 && !["ox", "cloze", "matching", "sequence"].includes(q.format) ? (
        <ul className="bank-units">{remainingPoints.map((unit) => <li key={unit}><AnswerPoints text={unit} readable /></li>)}</ul>
      ) : null}
      {answer.answerPairs.length ? (
        <ul className="bank-units">
          {pairs.map((pair) => (
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
            {answer.correctOrder.map(item => <li key={item}><AnswerPoints text={item} readable /></li>)}
          </ol>
        </section>
      ) : null}
      {answer.jokboSlides?.some(slide => slide.primary) ? (
        <BankJokboSlides key={`core:${q.question_id}`} slides={answer.jokboSlides} preload={preload} />
      ) : null}
      <div className={answer.slides.some(slide => slide.primary) && answer.jokboSlides?.length && !answer.jokboSlides.some(slide => slide.primary)
        ? "bank-evidence-pair" : "bank-evidence-stack"}>
        <BankSlides key={`${q.question_id}:${answer.slides.map(slide => slide.url).join("|")}`} slides={answer.slides} preload={preload} statusKnown={!!answer.evidenceStatus} />
        {!answer.jokboSlides?.some(slide => slide.primary) ? (
          <BankJokboSlides key={`ref:${q.question_id}`} slides={answer.jokboSlides} preload={preload}
            collapseReferences={!!answer.evidenceStatus && !answer.slides.some(slide => slide.primary)} />
        ) : null}
      </div>
      {hasReviewNotes ? (
        <details className="bank-review-notes" key={`review:${q.question_id}`}>
          <summary>문항 검수 기록</summary>
          {answer.reviewIssues?.map((issue, index) => <p key={index}><b>문항 검수 · 미해결</b> {issue}</p>)}
          {hasMedicalReview ? (
            <p>
              <b>외부지식 검토 · {review.verdict === "wrong" ? "틀림" : "의심"}</b> {review.note}
              {review.suggested_answer ? <><br />맞는 답: {review.suggested_answer}</> : null}
            </p>
          ) : null}
          <BankEvidenceNotice status={answer.evidenceStatus} />
          <BankSourceNote conflict={answer.conflict} external={answer.external} />
        </details>
      ) : null}
    </>
  );
}
