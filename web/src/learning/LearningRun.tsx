import { useEffect, useRef, useState } from "react";
import { Stem } from "../lecture/Stem";
import { shuffled } from "../bank/BankQuestion";
import { LearningFeedback, LearningReferences, SourceRefs } from "./LearningFeedback";
import type { LearningAnswer, LearningSession, RecallRating } from "../types/learning";

const LANES: Record<string, string> = { new: "새 내용", review: "복습", drill: "암기", mixed: "누적 복습", extra: "추가 학습", exam: "시험 연습" };
const promptText = (text: string) => text.replace(/\{\{c(\d+)\}\}/g, "[빈칸 $1]");
const RATINGS: { rating: RecallRating; label: string; hint: string }[] = [
  { rating: "Again", label: "다시", hint: "못 기억함 · 오답 · 찍음" },
  { rating: "Hard", label: "어려웠지만 맞힘", hint: "고민해서 기억함" },
  { rating: "Good", label: "맞힘", hint: "스스로 기억함" },
  { rating: "Easy", label: "쉽게 맞힘", hint: "바로 기억함" },
];

export function LearningRun({ session: s, busy, act, home }: { session: LearningSession; busy: boolean;
  act: (action: string, body: object) => void; home: () => void }) {
  const [answer, setAnswer] = useState<LearningAnswer>({});
  const [confidence, setConfidence] = useState<"sure" | "unsure" | "guess" | null>(null);
  const seconds = useRef(0);
  const answerRef = useRef(answer); answerRef.current = answer;
  const confidenceRef = useRef(confidence); confidenceRef.current = confidence;
  const feedbackRef = useRef<HTMLDivElement>(null);
  const draftKey = `studyez-learning-${s.sessionId}`;
  const q = s.question;
  useEffect(() => {
    let draft: { token?: string; seconds?: number; answer?: LearningAnswer; confidence?: "sure" | "unsure" | "guess" | null } = {};
    try { draft = JSON.parse(sessionStorage.getItem(draftKey) || "{}"); } catch { /* Storage is optional. */ }
    const resumed = draft.token === s.token;
    setAnswer(s.submittedAnswer ?? (resumed ? draft.answer : null) ?? { order: q ? shuffled(q.sequence_items, s.token ?? "") : [] });
    setConfidence(resumed ? draft.confidence ?? null : null);
    seconds.current = Math.max(s.activeSeconds ?? 0, resumed ? Math.min(900, Math.max(0, draft.seconds ?? 0)) : 0);
    window.scrollTo(0, 0);
  }, [s.token]);
  useEffect(() => { if (s.submittedAnswer) setAnswer(s.submittedAnswer); }, [s.submittedAnswer]);
  useEffect(() => {
    if (s.status !== "active") {
      try { sessionStorage.removeItem(draftKey); } catch { /* Storage is optional. */ }
      return;
    }
    let last = performance.now();
    const timer = window.setInterval(() => {
      const now = performance.now();
      if (document.visibilityState === "visible" && document.hasFocus()) seconds.current += Math.min(2, (now - last) / 1000);
      try { sessionStorage.setItem(draftKey, JSON.stringify({ token: s.token, seconds: seconds.current,
        answer: answerRef.current, confidence: confidenceRef.current })); } catch { /* Storage is optional. */ }
      last = now;
    }, 1000);
    return () => window.clearInterval(timer);
  }, [s.token, s.status]);
  useEffect(() => {
    if (!s.token) return;
    try { sessionStorage.setItem(draftKey, JSON.stringify({ token: s.token, seconds: seconds.current, answer, confidence })); }
    catch { /* Storage is optional. */ }
  }, [answer, confidence, s.token]);
  useEffect(() => {
    if (s.submitted && s.feedback) feedbackRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [s.submitted, s.token]);
  const ack = (selfCorrect?: boolean, reviewRating?: RecallRating) => act("acknowledge", { token: s.token, selfCorrect, reviewRating, activeSeconds: Math.floor(seconds.current) });
  const picked = answer.selected ?? [];
  const choose = (id: string) => setAnswer({ ...answer, selected: q?.format === "multi_select" ? picked.includes(id) ? picked.filter(x => x !== id) : [...picked, id] : [id] });
  const ready = !q || (q.options.length ? picked.length > 0 : q.format === "ox" ? Boolean(answer.text)
    : q.format === "matching" ? q.matching_left.every(l => answer.pairs?.[l]) : true);
  const showRecall = !s.optionsShown && Boolean(s.recallPrompt);
  const textRecall = Boolean(q && ["basic", "cloze", "list"].includes(q.format));
  const selfCheck = Boolean(s.submitted && q && s.feedback?.correct == null && s.mode !== "exam");
  const submit = () => act("submit", { token: s.token, confidence, answer: q ? answer : {}, activeSeconds: Math.floor(seconds.current) });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (busy || s.status !== "active" || e.ctrlKey || e.metaKey || e.altKey
        || (e.target instanceof HTMLElement && (e.target.isContentEditable || /INPUT|TEXTAREA|SELECT|BUTTON|A|SUMMARY/.test(e.target.tagName)))) return;
      if (!s.submitted && q?.options.length && /^[a-h1-8]$/i.test(e.key)) {
        const index = /^[1-8]$/.test(e.key) ? Number(e.key) - 1 : e.key.toUpperCase().charCodeAt(0) - 65;
        if (q.options[index]) { e.preventDefault(); choose(q.options[index].id); }
      } else if (!s.submitted && ready && !showRecall && (e.key === " " || e.key === "Enter")) { e.preventDefault(); submit(); }
      else if (s.submitted && s.mode !== "exam" && /^[1-4]$/.test(e.key)) {
        const rating = RATINGS[Number(e.key) - 1].rating;
        if (s.reviewChoices?.some(c => c.rating === rating)) { e.preventDefault(); ack(selfCheck ? rating !== "Again" : undefined, rating); }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [answer, confidence, busy, s.token, s.submitted, s.status, s.reviewChoices]);
  if (s.status === "complete") return <>
    <section className="learning-plan learning-complete"><h2>학습을 마쳤어요</h2>
      <p><strong>{s.summary?.completed ?? 0}개 완료</strong>{s.summary?.graded ? ` · 정답 ${s.summary.correct} / ${s.summary.graded}` : ""}</p>
      <div className="learning-actions"><button className="primary" onClick={home}>학습 현황으로</button>{s.canUndo ? <button disabled={busy} onClick={() => act("undo", {})}>마지막 평가 되돌리기</button> : null}</div>
      <details><summary>학습 기록</summary><p>새로 공부한 요점 {s.summary?.newObjectives ?? 0}개 · 시간을 두고 기억한 요점 {s.summary?.delayedRecall ?? 0}개</p>
        <p>오늘 공부는 어땠나요?</p><div className="learning-actions">{([["light", "가벼웠어요"], ["okay", "적당했어요"], ["heavy", "버거웠어요"]] as const).map(([value, label]) => <button aria-pressed={s.summary?.burden === value} key={value} disabled={busy} onClick={() => act("end", { burden: value })}>{label}</button>)}</div></details>
    </section>
    {s.results?.map((r, i) => <article className="learning-exam-result" key={i}><p>{r.title}</p><h3><Stem text={promptText(r.question.question)} /></h3>
      <ul>{r.question.options.map(o => <li key={o.id}><b>{o.id}</b> <Stem text={o.text} />{r.submittedAnswer.selected?.includes(o.id) ? " · 내 선택" : ""}</li>)}</ul>
      <div className="learning-study-layout has-references"><LearningFeedback value={r} picked={r.submittedAnswer.selected} /><LearningReferences value={r} /></div></article>)}
  </>;
  return <>
    <div className="learning-run-bar"><div><span className="learning-lane">{LANES[s.lane ?? ""] ?? "학습"}</span><strong>{s.index + 1} <span>/ {s.total}</span></strong></div>
      <div className="learning-run-tools">{s.canUndo && !s.submitted ? <button disabled={busy} onClick={() => act("undo", {})}>되돌리기</button> : null}
        <button disabled={busy} onClick={() => act("end", { token: s.token, activeSeconds: Math.floor(seconds.current) })}>마치기</button></div></div>
    <progress className="learning-run-progress" aria-label="이번 학습 진행" max={Math.max(1, s.total)} value={s.index} />
    <div className={`learning-study-layout${s.feedback ? " has-references" : ""}`}>
      <article className="learning-question">
        <h2><Stem text={promptText(showRecall ? s.recallPrompt! : q?.question ?? s.objective ?? "설명 학습")} /></h2>
        {q?.format === "multi_select" && !s.submitted ? <p className="learning-muted">해당하는 보기를 모두 고르세요.</p> : null}
        {s.mode === "exam" && !s.submitted ? <p className="learning-muted">정답은 시험 연습을 마친 뒤 공개됩니다.</p> : null}
        {showRecall ? <button disabled={busy} onClick={() => act("action", { token: s.token, action: "options" })}>보기 펼치기</button> : null}
        {q?.options.length ? <div className="learning-options">{q.options.map(o => {
          const correct = Boolean(s.feedback?.correctOptionIds?.includes(o.id));
          const wrong = Boolean(s.feedback && picked.includes(o.id) && !correct);
          return <button className={correct ? "is-correct" : wrong ? "is-wrong" : ""} key={o.id} aria-pressed={picked.includes(o.id)} disabled={busy || s.submitted} onClick={() => choose(o.id)}>
            <b>{o.id}</b><span><Stem text={o.text} /></span>{correct ? <small>✓ 정답</small> : wrong ? <small>내 선택</small> : null}</button>;
        })}</div> : null}
        {q?.format === "ox" ? <div className="learning-actions">{["O", "X"].map(v => <button key={v} disabled={busy || s.submitted} aria-pressed={answer.text === v} onClick={() => setAnswer({ text: v })}>{v}</button>)}</div> : null}
        {q?.format === "matching" ? <div className="learning-matching">{q.matching_left.map(l => <label key={l}>{l}<select aria-label={`${l}의 짝`} disabled={busy || s.submitted} value={answer.pairs?.[l] ?? ""} onChange={e => setAnswer({ pairs: { ...answer.pairs, [l]: e.target.value } })}><option value="">짝 선택</option>{shuffled(q.matching_right, s.token ?? "").map(r => <option key={r}>{r}</option>)}</select></label>)}</div> : null}
        {q?.format === "sequence" ? <ol>{(answer.order ?? []).map((item, i) => <li key={item} className="learning-sequence">{item}<button disabled={busy || s.submitted || i === 0} aria-label={`${item} 위로`} onClick={() => {
          const order = [...(answer.order ?? [])]; [order[i - 1], order[i]] = [order[i], order[i - 1]]; setAnswer({ order });
        }}>↑</button></li>)}</ol> : null}
        {textRecall && !s.submitted ? <details className="learning-recall"><summary>답 메모</summary><textarea aria-label="답 메모" value={answer.text ?? ""} onChange={e => setAnswer({ text: e.target.value })} placeholder="떠올린 답을 적어도 돼요" /></details> : null}
        {s.help ? <details className="learning-help" open><summary>설명 · 도움 사용</summary><p><Stem text={s.help.explanation || s.help.context || "별도 설명이 없는 문항입니다. 정답을 확인하세요."} /></p><p><b>기억할 내용</b> <Stem text={s.help.minimum} /></p><SourceRefs refs={s.help.source_refs} /></details> : null}
        {selfCheck && answer.text?.trim() ? <details className="learning-answer-memo"><summary>내 답 메모</summary><p>{answer.text}</p></details> : null}
        {s.feedback ? <div ref={feedbackRef}><LearningFeedback value={s.feedback} picked={picked} /></div> : null}
      </article>
      {s.feedback ? <LearningReferences value={s.feedback} subject={s.subject} runId={s.runId} /> : null}
    </div>
    <footer className="learning-controls">
      {!s.submitted && !showRecall ? <div className="learning-answer-actions"><div className="learning-secondary-actions">
        {s.mode !== "exam" && !s.help && q ? <button disabled={busy} onClick={() => act("action", { token: s.token, action: "help" })}>설명 보기</button> : null}
        {q ? <details className="learning-confidence"><summary>확신 기록</summary><div className="learning-confidence-actions">{([["sure", "확실"], ["unsure", "헷갈림"], ["guess", "모름·찍음"]] as const).map(([value, label]) => <button disabled={busy} aria-pressed={confidence === value} key={value} onClick={() => setConfidence(confidence === value ? null : value)}>{label}</button>)}</div></details> : null}</div>
        <button className="primary learning-reveal" disabled={busy || !ready} onClick={submit}>{q ? s.mode === "exam" ? "답변 저장" : "정답 보기" : "설명 보기"}</button></div> : null}
      {s.submitted ? q && s.mode !== "exam" && s.reviewChoices ? <>
        <div className="learning-rating-heading"><strong>기억 평가</strong><details><summary>평가 기준</summary><p>정답을 보기 전에 얼마나 기억했는지 고르세요. 오답·찍음·도움 받은 답은 ‘다시’입니다. 어렵게 맞힌 답도 기억 성공입니다.</p></details></div>
        <div className="learning-rating-buttons">{RATINGS.map((r, index) => {
          const choice = s.reviewChoices?.find(c => c.rating === r.rating);
          return <button className={`rating-${r.rating.toLowerCase()}`} disabled={busy || !choice} key={r.rating} title={`${index + 1} · ${r.hint}`} aria-keyshortcuts={String(index + 1)} onClick={() => ack(selfCheck ? r.rating !== "Again" : undefined, r.rating)}>
            <strong>{r.label}</strong><small>{choice ? `${Math.round(choice.intervalDays)}일 뒤` : "선택 불가"}</small></button>;
        })}</div></> : <div className="learning-actions">{selfCheck ? <><button disabled={busy} onClick={() => ack(false)}>다시</button><button className="primary" disabled={busy} onClick={() => ack(true)}>맞힘 · 다음</button></> : <button className="primary" disabled={busy} onClick={() => ack()}>{s.mode === "exam" ? "다음 문제" : "다음으로"}</button>}</div> : null}
    </footer>
  </>;
}
