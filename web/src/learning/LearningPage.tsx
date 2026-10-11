import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { invalidateTimetable } from "../firstScreen";
import { Stem } from "../lecture/Stem";
import { shuffled } from "../bank/BankQuestion";
import type { LearningAnswer, LearningDashboard, LearningFeedback, LearningSession, SourceRef } from "../types/learning";
import "../styles/learning.css";

const ROOT = "/api/learning";
const LANES: Record<string, string> = { new: "새 범위", review: "기억 되살리기", drill: "짧은 암기", mixed: "누적 확인", extra: "추가 학습", exam: "시험 연습" };
const fmt = (seconds: number) => `${Math.floor(seconds / 60)}분 ${seconds % 60}초`;
const promptText = (text: string) => text.replace(/\{\{c(\d+)\}\}/g, "[빈칸 $1]");

export function LearningPage() {
  const { subject, runId } = useParams();
  const [params, setParams] = useSearchParams();
  const sid = params.get("session");
  const [dashboard, setDashboard] = useState<LearningDashboard | null>(null);
  const [session, setSession] = useState<LearningSession | null>(null);
  const [minutes, setMinutes] = useState(60);
  const [buffer, setBuffer] = useState(3);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [available, setAvailable] = useState(true);
  const scope = new URLSearchParams(subject && runId ? { subject, runId } : {});
  const scopeQuery = scope.toString();
  const load = useCallback(async () => {
    const availability = await api<{ enabled: boolean }>(`${ROOT}/availability`);
    setAvailable(availability.enabled);
    if (!availability.enabled) return;
    if (sid) setSession(await api<LearningSession>(`${ROOT}/sessions/${sid}`));
    else {
      setSession(null);
      const info = await api<LearningDashboard>(`${ROOT}/dashboard?${scopeQuery}`);
      setDashboard(info); setMinutes(info.minutes); setBuffer(info.bufferDays);
    }
  }, [sid, scopeQuery]);
  useEffect(() => { void load().catch(e => setError(e.message)); }, [load]);
  const run = async (work: () => Promise<void>) => {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try { await work(); } catch (e) { setError((e as Error).message); }
    finally { lock.current = false; setBusy(false); }
  };
  const start = (mode: "daily" | "extra" | "exam") => run(async () => {
    const result = await api<{ sessionId: string }>(`${ROOT}/sessions`, { method: "POST", body: JSON.stringify({ mode, subject, runId }) });
    setParams({ session: result.sessionId });
  });
  const mutation = async (action: string, body: object) => {
    const updated = await api<LearningSession>(`${ROOT}/sessions/${sid}/${action}`, { method: "POST", body: JSON.stringify(body) });
    setSession(updated);
    invalidateTimetable();
  };
  const legacy = subject && runId ? `/bank/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}?classic=1` : "/";
  if (!available) return <section className="learning"><h1>학습</h1><p>새 학습 기능이 현재 꺼져 있습니다.</p><Link to={legacy}>기존 학습으로</Link></section>;
  return <section className="learning">
    <header className="learning-header"><div><span className="learning-eyebrow">Study EZ</span><h1>{session?.mode === "exam" ? "시험 연습" : subject ? "강의 학습" : "오늘의 학습"}</h1></div>
      <nav><Link to="/study">전체 학습</Link><Link to="/">캘린더</Link>{subject ? <Link to={legacy}>기존 풀이</Link> : null}</nav></header>
    {error ? <p role="alert" className="notice is-error">{error} <button onClick={() => void run(load)}>다시 불러오기</button></p> : null}
    {sid && session ? <LearningRun key={session.sessionId} session={session} busy={busy}
      act={(action, body) => void run(() => mutation(action, body))} home={() => setParams({})} /> : sid ? <p>학습을 불러오는 중…</p> : dashboard ? <>
      <section className="learning-plan">
        <div><span className="learning-eyebrow">오늘의 약속</span><h2>{dashboard.plan.complete ? "오늘 계획을 마쳤어요" : `${Math.round(dashboard.plan.budgetSeconds / 60)}분 안에서 한 걸음씩`}</h2>
          <p>전체 계획 {dashboard.plan.completed.length} / {dashboard.plan.entries.length}개 활동 완료 · {fmt(dashboard.plan.activeSeconds)} 학습</p>
          <progress aria-label="오늘 활동 완료" max={Math.max(1, dashboard.plan.entries.length)} value={dashboard.plan.completed.length} /></div>
        <div className="learning-actions">
          {dashboard.activeSession ? <button className="primary" onClick={() => setParams({ session: dashboard.activeSession! })}>진행 중 학습 이어가기</button> : null}
          {!dashboard.plan.complete && dashboard.plan.remaining > 0 ? <button className="primary" disabled={busy || !dashboard.enabled} onClick={() => void start("daily")}>오늘 학습 시작 · {dashboard.plan.remaining}개 활동</button> : null}
          <button disabled={busy || !dashboard.enabled || !dashboard.progress.total} onClick={() => void start("extra")}>원하는 만큼 더 공부하기</button>
          <button disabled={busy || !dashboard.enabled || dashboard.examQuestions === 0} onClick={() => void start("exam")}>처음 보는 객관식 · {dashboard.examQuestions}개 요점</button>
        </div>
        {subject && !dashboard.plan.remaining && !dashboard.plan.complete ? <p>이 강의는 오늘 배정된 활동이 없습니다. <Link to="/study">전체 계획</Link>에서 이어가거나 추가 학습을 선택하세요.</p> : null}
        {dashboard.examQuestions === 0 ? <p className="learning-muted">배운 범위에 아직 보지 않은 시험용 객관식이 준비되면 시험 연습을 시작할 수 있습니다.</p> : null}
        {dashboard.plan.infeasible ? <p className="learning-warning">첫 회독 목표일까지 새 범위에 하루 약 {dashboard.plan.newRequiredMinutes}분이 필요합니다. 가용시간이나 첫 회독 여유일을 조정해 주세요.</p> : null}
      </section>
      <div className="learning-metrics">
        <article><strong>{dashboard.progress.covered} / {dashboard.progress.total}</strong><span>처음 학습한 요점</span></article>
        <article><strong>{dashboard.progress.delayedRecall}</strong><span>간격을 두고 두 번 확인한 요점</span></article>
        <article><strong>{dashboard.progress.questionGaps}</strong><span>학습 문항이 필요한 요점</span></article>
      </div>
      {dashboard.progress.legacyObjectives ? <p className="learning-muted">기존 자료는 문항별로 집계합니다. 전체 강의 범위 확인은 새 학습요점 목록이 준비된 뒤 가능합니다. 과거 자기평가는 새 문항 정답률로 환산하지 않습니다.</p> : null}
      {dashboard.scopeOnlyLectures?.length ? <details className="learning-panel"><summary>학습 대상 요점이 없는 강의 · {dashboard.scopeOnlyLectures.length}개</summary>
        <p>범위 제외 근거가 등록된 강의입니다. 학습 완료나 기억한 요점 수에 포함하지 않습니다.</p>
        {dashboard.scopeOnlyLectures.map(l => <details key={`${l.subject}/${l.runId}`}><summary>{l.title}</summary>
          {l.ranges.map((r, i) => <p key={i}><b>{r.status === "uncertain" ? "검토 필요 · " : ""}{r.title}</b> · {r.reason}<br /><SourceRefs refs={r.source_refs} /></p>)}
          <Link to={`/lectures/${encodeURIComponent(l.subject)}/${encodeURIComponent(l.runId)}`}>원본 강의 자료 확인</Link>
        </details>)}</details> : null}
      {dashboard.missingLectures.length || dashboard.uncertainRanges ? <details className="learning-panel"><summary>자료 미준비 {dashboard.missingLectures.length}강의 · 범위 확인 필요 {dashboard.uncertainRanges}개</summary>
        <ul>{dashboard.missingLectures.map((l, i) => <li key={i}>{l.date} · {l.title}</li>)}</ul><p>자료가 준비되지 않은 범위는 학습 완료로 처리하지 않습니다.</p></details> : null}
      <details className="learning-panel"><summary>공부 시간과 계획 설정</summary>
        <div className="learning-settings"><label>하루 총시간 <input type="number" min={5} max={480} value={minutes} onChange={e => setMinutes(Number(e.target.value))} /> 분</label>
          <label>시험 전 첫 회독 여유 <input type="number" min={0} max={14} value={buffer} onChange={e => setBuffer(Number(e.target.value))} /> 일</label></div>
        <p>모든 강의가 이 시간을 함께 사용합니다. 오늘 계획을 조정해도 완료한 활동은 유지됩니다.</p>
        <div className="learning-actions"><button disabled={busy} onClick={() => void run(async () => {
          await api(`${ROOT}/settings`, { method: "PUT", body: JSON.stringify({ minutes, bufferDays: buffer, enabled: true, replan: false }) }); await load();
        })}>다음 계획부터 적용</button><button disabled={busy || Boolean(dashboard.activeSession)} onClick={() => void run(async () => {
          await api(`${ROOT}/settings`, { method: "PUT", body: JSON.stringify({ minutes, bufferDays: buffer, enabled: true, replan: true }) }); await load();
        })}>오늘 남은 계획도 조정</button></div>
      </details>
      <details className="learning-panel"><summary>강의별 범위 보기</summary><div className="learning-lectures">{dashboard.lectures.map(l => <Link key={`${l.subject}/${l.runId}`} to={`/bank/${encodeURIComponent(l.subject)}/${encodeURIComponent(l.runId)}`}>
        <span>{l.title}</span><strong>{l.covered} / {l.total}</strong></Link>)}</div></details>
      <details className="learning-panel"><summary>학습요점과 강의 흐름 찾기</summary><label>학습요점 검색 <input value={search} onChange={e => setSearch(e.target.value)} placeholder="개념이나 강의 이름" /></label>
        <ul className="learning-objectives">{dashboard.objectives.filter(o => `${o.title} ${o.lecture}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())).slice(0, 100).map(o => <li key={o.key}>
          <strong>{o.covered ? "✓ " : "○ "}{o.title}</strong><p>{o.lecture}</p><SourceRefs refs={o.sourceRefs} />
          {o.related.length ? <p>선행 요점: {o.related.map(k => dashboard.objectives.find(x => x.key === k)?.title).filter(Boolean).join(" · ")}</p> : null}</li>)}</ul>
        <p className="learning-muted">최대 100개씩 표시합니다. 같은 이름이어도 강의별 맥락과 학습 기록은 구분합니다.</p></details>
    </> : <p>학습 계획을 준비하는 중…</p>}
  </section>;
}

function SourceRefs({ refs }: { refs?: SourceRef[] }) {
  return refs?.length ? <small className="learning-muted">근거: {refs.map(r => `${r.source_id === "EXT" ? "외부 지식" : r.source_id} ${r.locator}`).join(" · ")}</small> : null;
}

function Feedback({ value, picked = [] }: { value: LearningFeedback; picked?: string[] }) {
  const explanations = value.optionExplanations ?? [];
  const distractor = explanations.find(e => !value.correctOptionIds?.includes(e.option_id)
    && picked.includes(e.option_id)) ?? explanations.find(e => !value.correctOptionIds?.includes(e.option_id));
  const focused = explanations.filter(e => value.correctOptionIds?.includes(e.option_id)
    || picked.includes(e.option_id) || e === distractor);
  return <section className="learning-feedback" aria-label="정답과 해설">
    {value.correct !== undefined && value.correct !== null ? <p className="learning-verdict">{value.correct ? "맞았습니다" : "차이를 확인해 볼까요"}{value.confidence === "guess" ? " · 찍은 답은 다시 확인합니다" : ""}</p> : null}
    {value.answer ? <p><Stem text={value.answer} /></p> : null}
    {focused.map(e => <p key={e.option_id}><b>{e.option_id}</b> <Stem text={e.text} /></p>)}
    {!explanations.length && value.answerUnits?.length ? <ul>{value.answerUnits.map((a, i) => <li key={i}><Stem text={a} /></li>)}</ul> : null}
    {value.answerPairs?.length ? <ul>{value.answerPairs.map((p, i) => <li key={i}>{p.left} → {p.right}</li>)}</ul> : null}
    {value.correctOrder?.length ? <p>{value.correctOrder.join(" → ")}</p> : null}
    {explanations.length > focused.length ? <details><summary>모든 선지 해설</summary>{explanations.map(e => <p key={e.option_id}><b>{e.option_id}</b> <Stem text={e.text} /></p>)}</details> : null}
    {value.explanation ? <details><summary>맥락과 설명</summary><p><Stem text={value.explanation} /></p><p><b>기억할 내용</b> <Stem text={value.minimum} /></p></details> : null}
    {value.sourceConflict ? <p className="learning-warning">자료 충돌: {value.sourceConflict}</p> : null}
    {value.medicalReview && value.medicalReview.verdict !== "ok" ? <p className="learning-warning">정답 검토 · {value.medicalReview.note}<br />{value.medicalReview.suggested_answer}</p> : null}
    <SourceRefs refs={value.sourceRefs} />
  </section>;
}

function LearningRun({ session: s, busy, act, home }: { session: LearningSession; busy: boolean;
  act: (action: string, body: object) => void; home: () => void }) {
  const [answer, setAnswer] = useState<LearningAnswer>({});
  const [elapsed, setElapsed] = useState(0);
  const seconds = useRef(0);
  const answerRef = useRef(answer);
  answerRef.current = answer;
  const draftKey = `studyez-learning-${s.sessionId}`;
  const q = s.question;
  useEffect(() => {
    let draft: { token?: string; seconds?: number; answer?: LearningAnswer } = {};
    try { draft = JSON.parse(sessionStorage.getItem(draftKey) || "{}"); } catch { /* Storage is optional. */ }
    const resumed = draft.token === s.token;
    setAnswer(s.submittedAnswer ?? (resumed ? draft.answer : null) ?? { order: q ? shuffled(q.sequence_items, s.token ?? "") : [] });
    seconds.current = Math.max(s.activeSeconds ?? 0, resumed ? Math.min(900, Math.max(0, draft.seconds ?? 0)) : 0);
    setElapsed(Math.floor(seconds.current));
    window.scrollTo(0, 0);
  }, [s.token]); // submitting/revealing must not clear the original choice
  useEffect(() => { if (s.submittedAnswer) setAnswer(s.submittedAnswer); }, [s.submittedAnswer]);
  useEffect(() => {
    if (s.status !== "active") {
      try { sessionStorage.removeItem(draftKey); } catch { /* Storage is optional. */ }
      return;
    }
    let last = performance.now();
    const timer = window.setInterval(() => {
      const now = performance.now();
      if (document.visibilityState === "visible" && document.hasFocus()) {
        seconds.current += Math.min(2, (now - last) / 1000); setElapsed(Math.floor(seconds.current));
      }
      try { sessionStorage.setItem(draftKey, JSON.stringify({ token: s.token, seconds: seconds.current, answer: answerRef.current })); } catch { /* Storage is optional. */ }
      last = now;
    }, 1000);
    return () => window.clearInterval(timer);
  }, [s.token, s.status]);
  const ack = (selfCorrect?: boolean) => act("acknowledge", { token: s.token, selfCorrect, activeSeconds: Math.floor(seconds.current) });
  if (s.status === "complete") return <>
    <section className="learning-plan"><span className="learning-eyebrow">이번 학습</span><h2>여기까지 공부했어요</h2>
      <p>활동 {s.summary?.completed ?? 0}개 · {fmt(s.seconds)}</p>
      <div className="learning-metrics"><article><strong>{s.summary?.newObjectives ?? 0}</strong><span>새로 접한 요점</span></article><article><strong>{s.summary?.delayedRecall ?? 0}</strong><span>시간을 두고 다시 기억한 요점</span></article></div>
      {s.summary?.graded ? <p>채점 문항 {s.summary.correct} / {s.summary.graded} · 처음 본 문항에서 도움 없이 정답 {s.summary.freshCorrect} / {s.summary.freshGraded}</p> : <p>설명 학습과 자기평가는 객관식 정답률에 포함하지 않습니다.</p>}
      <p>오늘 공부의 부담은 어땠나요? <span className="learning-muted">선택 사항</span></p>
      <div className="learning-actions">{([["light", "가벼웠어요"], ["okay", "적당했어요"], ["heavy", "버거웠어요"]] as const).map(([value, label]) => <button aria-pressed={s.summary?.burden === value} key={value} disabled={busy} onClick={() => act("end", { burden: value })}>{label}</button>)}</div>
      <div className="learning-actions"><button className="primary" onClick={home}>학습 현황으로</button>{s.canUndo ? <button disabled={busy} onClick={() => act("undo", {})}>마지막 평가 되돌리기</button> : null}</div>
    </section>
    {s.results?.map((r, i) => <article className="learning-panel" key={i}><p>{r.title}</p><h3><Stem text={promptText(r.question.question)} /></h3>
      <ul>{r.question.options.map(o => <li key={o.id}><b>{o.id}</b> <Stem text={o.text} />{r.submittedAnswer.selected?.includes(o.id) ? " · 내 선택" : ""}</li>)}</ul>
      <Feedback value={r} picked={r.submittedAnswer.selected} /></article>)}
  </>;
  const picked = answer.selected ?? [];
  const choose = (id: string) => setAnswer({ ...answer, selected: q?.format === "multi_select" ? picked.includes(id) ? picked.filter(x => x !== id) : [...picked, id] : [id] });
  const ready = !q || (q.options.length ? picked.length > 0 : q.format === "ox" ? Boolean(answer.text)
    : q.format === "matching" ? q.matching_left.every(l => answer.pairs?.[l]) : true);
  const showRecall = !s.optionsShown && Boolean(s.recallPrompt);
  return <>
    <div className="learning-run-bar"><span>{LANES[s.lane ?? ""]} · {s.index + 1} / {s.total}</span><span>{fmt(elapsed)}</span></div>
    {s.mode !== "exam" ? <p className="learning-context">{s.lecture}</p> : null}
    <article className="learning-question">
      <h2><Stem text={promptText(showRecall ? s.recallPrompt! : q?.question ?? s.objective ?? "설명 학습")} /></h2>
      {showRecall ? <><p className="learning-muted">잠깐 떠올려 본 뒤 보기를 확인하세요. 바로 펼쳐도 됩니다.</p><button disabled={busy} onClick={() => act("action", { token: s.token, action: "options" })}>보기 펼치기</button></> : null}
      {q?.options.length ? <div className="learning-options">{q.options.map(o => <button key={o.id} aria-pressed={picked.includes(o.id)} disabled={busy || s.submitted} onClick={() => choose(o.id)}><b>{o.id}</b><Stem text={o.text} /></button>)}</div> : null}
      {q?.format === "ox" ? <div className="learning-actions">{["O", "X"].map(v => <button key={v} disabled={busy || s.submitted} aria-pressed={answer.text === v} onClick={() => setAnswer({ text: v })}>{v}</button>)}</div> : null}
      {q?.format === "matching" ? <div className="learning-matching">{q.matching_left.map(l => <label key={l}>{l}<select aria-label={`${l}의 짝`} disabled={busy || s.submitted} value={answer.pairs?.[l] ?? ""} onChange={e => setAnswer({ pairs: { ...answer.pairs, [l]: e.target.value } })}><option value="">선택</option>{shuffled(q.matching_right, s.token ?? "").map(r => <option key={r}>{r}</option>)}</select></label>)}</div> : null}
      {q?.format === "sequence" ? <ol>{(answer.order ?? []).map((item, i) => <li key={item} className="learning-sequence">{item}<button disabled={busy || s.submitted || i === 0} aria-label={`${item} 위로`} onClick={() => {
        const order = [...(answer.order ?? [])]; [order[i - 1], order[i]] = [order[i], order[i - 1]]; setAnswer({ order });
      }}>↑</button></li>)}</ol> : null}
      {q && ["basic", "cloze", "list"].includes(q.format) && !s.submitted ? <label className="learning-recall">떠올린 답 <small>입력은 선택 사항입니다</small><textarea value={answer.text ?? ""} onChange={e => setAnswer({ text: e.target.value })} placeholder="머릿속으로 답해도 됩니다" /></label> : null}
      {s.mode !== "exam" && !s.submitted && !s.help ? <div className="learning-actions learning-help-actions"><button disabled={busy} onClick={() => act("action", { token: s.token, action: "help" })}>이해가 안 돼요</button><button disabled={busy} onClick={() => act("action", { token: s.token, action: "help" })}>무엇을 외워야 하나요?</button></div> : null}
      {s.help ? <aside className="learning-help"><p>{s.help.context}</p><p><Stem text={s.help.explanation || "이 기존 문항에는 별도의 이해 설명이 없습니다. 정답과 원본을 확인한 뒤 다음 범위로 넘어갈 수 있습니다."} /></p><p><b>기억할 내용</b> <Stem text={s.help.minimum} /></p><p className="learning-muted">{s.help.rationale}</p><SourceRefs refs={s.help.source_refs} /></aside> : null}
      {s.assisted ? <p className="learning-muted">도움을 받은 학습으로 기록합니다. 다음에는 도움 없이 확인합니다.</p> : null}
      {s.feedback ? <Feedback value={s.feedback} picked={picked} /> : null}
      {s.subject && s.runId && (s.feedback || s.help) ? <p><Link target="_blank" to={`/lectures/${encodeURIComponent(s.subject)}/${encodeURIComponent(s.runId)}`}>원본 강의 자료 열기 ↗</Link></p> : null}
    </article>
    <footer className="learning-controls">
      {!s.submitted && !showRecall ? <><p>{q ? "정답을 보기 전, 얼마나 확신하나요?" : "설명을 확인하고 다음으로 이어가세요."}</p><div className="learning-actions">
        {q ? ([["sure", "확실함"], ["unsure", "헷갈림"], ["guess", "찍음"]] as const).map(([value, label]) => <button className={value === "sure" ? "primary" : ""} disabled={busy || !ready} key={value} onClick={() => act("submit", { token: s.token, confidence: value, answer, activeSeconds: Math.floor(seconds.current) })}>{label} · 제출</button>)
          : <button className="primary" disabled={busy} onClick={() => act("submit", { token: s.token, confidence: "unsure", answer: {}, activeSeconds: Math.floor(seconds.current) })}>설명 확인</button>}
      </div></> : null}
      {s.submitted ? <div className="learning-actions">{s.mode !== "exam" && q && s.feedback?.correct == null ? <><button disabled={busy} onClick={() => ack(false)}>기억하지 못했어요</button><button className="primary" disabled={busy} onClick={() => ack(true)}>스스로 맞혔어요</button></> : <button className="primary" disabled={busy} onClick={() => ack()}>{s.mode === "exam" ? "답변 저장 · 다음" : "확인했어요 · 다음"}</button>}</div> : null}
      <div className="learning-actions">{s.canUndo && !s.submitted ? <button disabled={busy} onClick={() => act("undo", {})}>이전 평가 되돌리기</button> : null}<button disabled={busy} onClick={() => act("end", { token: s.token, activeSeconds: Math.floor(seconds.current) })}>여기서 마치기</button></div>
    </footer>
  </>;
}
