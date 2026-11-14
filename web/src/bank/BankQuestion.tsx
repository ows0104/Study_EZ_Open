import { useRef, useState } from "react";
import { Stem } from "../lecture/Stem";
import type { BankAnswer, BankQuestion } from "../types/bank";
import type { SlidePreloader } from "../slidePreload";
import { AnswerPoints, answerPoints } from "./AnswerPoints";
import { BankStem } from "./BankStem";
import { BankSourceNote, SourceConflictBadge } from "./BankSourceNote";
import { BankSlides } from "./BankSlides";
import { BankJokboSlides } from "./BankJokboSlides";
import { BankEvidenceNotice } from "./BankEvidenceNotice";
import { matchingLayout, presentationSeed, shuffled } from "./presentation";
import "./review-notes.css";
export { shuffled } from "./presentation";

const letter = (index: number) => String.fromCharCode(65 + index);

function QuestionStimulus({image,onReady}:{image:NonNullable<BankQuestion['stimuli']>[number];onReady:(loaded:boolean)=>void}) {
  const [failed,setFailed]=useState(false);
  return failed?<p role="alert">문항 그림을 불러오지 못했습니다. 그림을 확인하기 전에는 회상 완료로 평가하지 마세요.</p>
    :<img src={image.url} alt={image.alt} width={image.width} height={image.height} onLoad={()=>onReady(true)} onError={()=>{setFailed(true);onReady(false);}}/>;
}

function QuestionStimuli({images,onReady}:{images:NonNullable<BankQuestion['stimuli']>;onReady?:(ready:boolean)=>void}) {
  const loaded=useRef(new Set<number>());const failed=useRef(false);
  return <div className="bank-stimuli">{images.map((s,i)=><figure key={s.sha256+':'+i}><QuestionStimulus image={s} onReady={ready=>{
    if(ready)loaded.current.add(i);else failed.current=true;
    onReady?.(!failed.current&&loaded.current.size===images.length);
  }}/></figure>)}</div>;
}

/** 객관식 선지는 저장 ID(A·B…) 대신 화면 순서 번호로 보인다(2026-11-12) — 키 1–4와 같은 번호. 저장·전송 값은 ID 그대로다. */
const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
export function optionNumbers(q: BankQuestion) {
  return new Map(q.options.map((option, index) => [option.id, String(index + 1)]));
}
/** 정답·해설 줄 앞의 선지 머리표(`B:`·`**B**:`·`B.`·`B)`)와 ID만 나열한 정답(`B`, `A, C`)을 번호로. 본문 속 글자는 원문 그대로. */
export function numberChoiceLabels(text: string, numbers: Map<string, string>) {
  if (!numbers.size) return text;
  const ids = [...numbers.keys()].sort((a, b) => b.length - a.length).map(escape).join("|");
  const list = new RegExp(String.raw`^\s*(?:${ids})(?:\s*[,·/]\s*(?:${ids}))*\s*$`);
  if (list.test(text)) return text.replace(new RegExp(`(?<![A-Za-z0-9])(${ids})(?![A-Za-z0-9])`, "g"), id => numbers.get(id)!);
  const head = new RegExp(String.raw`^(\s*(?:[-*]\s+)?)(\*\*)?(${ids})(\*\*)?(?=\s*[:：.)])`, "gm");
  return text.replace(head, (_m, lead: string, open: string | undefined, id: string, close: string | undefined) =>
    `${lead}${open ?? ""}${numbers.get(id)}${close ?? ""}`);
}

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
export function QuestionBody({ question: q, answer, picked, onPick, matching, sequence, showOptions = true, disabled = false, showChoiceScore = true,onStimuliReady, recallChoices, choiceCorrectIds, choiceHint = true, choiceNotes }: {
  question: BankQuestion;
  answer: BankAnswer | null;
  picked: Set<string>;
  onPick: (id: string) => void;
  matching?: import("react").ReactNode;
  sequence?: import("react").ReactNode;
  showOptions?: boolean;
  disabled?: boolean;
  showChoiceScore?: boolean;
  onStimuliReady?:(ready:boolean)=>void;
  /** 단답·나열에 덧붙인 선지(Main-Quiz 「선지 보기」). 주면 q.options 대신 그리고, 답을 본 뒤 선지마다 결과를 표시한다. */
  recallChoices?: { id: string; text: string }[];
  /** recallChoices의 정답 ID를 직접 줄 때(객관식 모드). 없으면 answer.recallCorrectIds. */
  choiceCorrectIds?: string[];
  /** 「하나를/모두 고르세요」 안내. 객관식 모드는 정답 개수를 알리지 않으려고 끈다. */
  choiceHint?: boolean;
  /** 덧붙인 선지의 오답마다 왜 틀렸나·족보 출처(답을 본 뒤). 고른 오답 아래에 보이고 나머지는 접어 둔다(2026-11-14 choices-merge). */
  choiceNotes?: Record<string, { why: string; source: string }>;
}) {
  const score = showChoiceScore ? choiceScore(q, answer, picked) : null;
  const options = recallChoices ?? q.options;
  const expected = recallChoices ? (choiceCorrectIds ?? answer?.recallCorrectIds) : answer?.correctOptionIds;
  const marked = recallChoices ? Boolean(answer && expected?.length) : Boolean(score);
  const notes = recallChoices && answer && showOptions ? choiceNotes ?? {} : {};
  const note = (id: string) => notes[id] ? <span className="bank-option-why">{notes[id].source ? <b>{notes[id].source}</b> : null}{notes[id].why}</span> : null;
  const otherNotes = options.filter(option => notes[option.id] && !picked.has(option.id));
  return (
    <>
      <BankStem text={q.question} list={q.format === "list"} cloze={q.format === "cloze"} answerUnits={answer?.answerUnits} />
      {!!q.stimuli?.length&&<QuestionStimuli key={q.question_id+q.stimuli.map(s=>s.sha256).join('')} images={q.stimuli} onReady={onStimuliReady}/>}
      {q.format === "ox" && !answer ? <p className="bank-note">O 인가 X 인가, 그리고 왜인가</p> : null}
      {q.mcq_mode === "recall_first" && !showOptions ? <p className="bank-note">기억 확인형 · 먼저 답을 떠올린 뒤 선지를 공개하세요.</p> : null}
      {recallChoices && choiceHint && showOptions && !answer ? <p className="bank-note">{q.format === "list" ? "해당하는 것을 모두 고르세요." : "하나를 고르세요."}</p> : null}
      {options.length && showOptions ? (
        <ul className="bank-options">
          {options.map((option, index) => {
            const selected = picked.has(option.id);
            const correct = expected?.includes(option.id);
            const result = marked ? correct ? selected ? "is-correct" : "is-missed" : selected ? "is-wrong" : "" : "";
            const label = marked ? correct ? selected ? "✓ 맞게 고른 정답" : "! 빠뜨린 정답 · 미선택"
              : selected ? "✕ 잘못 고른 선지" : "정답 아님 · 미선택" : "";
            const cls = `${selected ? " is-picked" : ""}${result ? ` ${result}` : ""}`;
            return (
              <li key={option.id}>
                <button type="button" className={`bank-option${cls}`} disabled={disabled || Boolean(answer)}
                  aria-pressed={selected} aria-keyshortcuts={index < 9 ? String(index + 1) : undefined} onClick={() => onPick(option.id)}>
                  <b>{index + 1}</b> {option.text}
                  {label ? <span className="bank-option-result">{label}</span> : null}
                </button>
                {selected ? note(option.id) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      {otherNotes.length ? (
        <details className="bank-option-why-more">
          <summary>다른 오답이 틀린 이유</summary>
          <ul>{otherNotes.map(option => <li key={option.id}><b>{options.indexOf(option) + 1}</b> {note(option.id)}</li>)}</ul>
        </details>
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

/** 문항 검수·외부지식·근거 상태·자료 차이. 답 영역 안(기존 은행) 또는 참고 슬라이드 아래(Main-Quiz)에 그린다. */
export function hasAnswerReview(answer: BankAnswer) {
  const review = answer.medicalReview;
  return Boolean(answer.reviewIssues?.length || (review && review.verdict !== "ok")
    || answer.evidenceStatus || answer.conflict?.trim() || answer.external);
}

export function AnswerReviewItems({ answer }: { answer: BankAnswer }) {
  const review = answer.medicalReview;
  return <>
    {answer.reviewIssues?.map((issue, index) => <p key={index}><b>문항 검수 · 미해결</b> {issue}</p>)}
    {review && review.verdict !== "ok" ? (
      <p>
        <b>외부지식 검토 · {review.verdict === "wrong" ? "틀림" : "의심"}</b> {review.note}
        {review.suggested_answer ? <><br />맞는 답: {review.suggested_answer}</> : null}
      </p>
    ) : null}
    <BankEvidenceNotice status={answer.evidenceStatus} />
    <BankSourceNote conflict={answer.conflict} external={answer.external} />
  </>;
}

/** `reviewInline={false}`: 검토 기록을 그리지 않는다 — 호출한 화면이 참고 슬라이드 아래에 따로 둔다.
 *  자료 충돌은 접힌 기록만으로는 놓치므로 답 위에 배지로 함께 보인다. */
export function AnswerBody({ question: q, answer, preload, reviewInline = true }: {
  question: BankQuestion; answer: BankAnswer; preload?: SlidePreloader; reviewInline?: boolean;
}) {
  const hasReviewNotes = reviewInline && hasAnswerReview(answer);
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
  const numbers = choice ? optionNumbers(q) : new Map<string, string>();
  const label = (text: string) => numberChoiceLabels(text, numbers);
  const extraChoiceUnits = remainingPoints.filter(unit => !linkedUnits.has(unit));
  return (
    <>
      {/* 검토 기록을 접어 따로 두는 화면(Main-Quiz)은 자료 충돌만 답 위에 배지로 띄운다(2026-11-13). */}
      {reviewInline ? null : <SourceConflictBadge answer={answer} />}
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
          <AnswerPoints text={label(answer.answer)} units={q.format === "ox" ? [] : answer.answerUnits.map(label)} readable list={q.format === "list"} />
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
            {q.options.map((option, index) => (
              <li key={option.id}>
                <p><b>{index + 1}</b> <Stem text={option.text} />
                  <span className="bank-note"> · {answer.correctOptionIds.includes(option.id) ? "정답 선지" : "정답이 아닌 선지"}</span>
                </p>
                {choiceUnits.has(option.id) ? choiceUnits.get(option.id)!.map((text, index) => (
                  <p key={index}><AnswerPoints text={text} readable /></p>
                )) : <p className="bank-note">이 선지에 등록된 해설이 없습니다.</p>}
              </li>
            ))}
            {extraChoiceUnits.map(unit => <li key={unit}><AnswerPoints text={label(unit)} readable /></li>)}
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
          <BankJokboSlides key={`ref:${q.question_id}`} slides={answer.jokboSlides} preload={preload} />
        ) : null}
      </div>
      {hasReviewNotes ? (
        <details className="bank-review-notes" key={`review:${q.question_id}`}>
          <summary>문항 검수 기록</summary>
          <AnswerReviewItems answer={answer} />
        </details>
      ) : null}
    </>
  );
}
