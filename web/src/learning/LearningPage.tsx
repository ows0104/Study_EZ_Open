import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { invalidateTimetable } from "../firstScreen";
import { Stem } from "../lecture/Stem";
import { shuffled } from "../bank/BankQuestion";
import { LearningOverview } from "./LearningOverview";
import { LectureWorkload, WorkloadSummary } from "./LearningWorkload";
import type { LearningAnswer, LearningDashboard, LearningFeedback, LearningSession, RecallRating, SourceRef } from "../types/learning";
import "../styles/learning.css";

const ROOT = "/api/learning";
const LANES: Record<string, string> = { new: "새 범위", review: "기억 되살리기", drill: "짧은 암기", mixed: "누적 확인", extra: "추가 학습", exam: "시험 연습" };
const fmt = (seconds: number) => `${Math.floor(seconds / 60)}분 ${seconds % 60}초`;
const promptText = (text: string) => text.replace(/\{\{c(\d+)\}\}/g, "[빈칸 $1]");
const RATING_LABELS: Record<RecallRating, string> = { Again: "다시 · 못 기억함/찍음", Hard: "어려웠지만 맞힘", Good: "맞힘", Easy: "쉽게 맞힘" };

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
  const timeLimitReached = dashboard && dashboard.plan.activeSeconds >= dashboard.plan.budgetSeconds
    && dashboard.plan.completed.length < dashboard.plan.entries.length;
  if (!available) return <section className="learning"><h1>학습</h1><p>새 학습 기능이 현재 꺼져 있습니다.</p><Link to={legacy}>기존 학습으로</Link></section>;
  return <section className="learning">
    <header className="learning-header"><div><span className="learning-eyebrow">Study EZ{subject ? " · 강의 학습" : ""}</span><h1>{session?.mode === "exam" ? "시험 연습" : subject ? dashboard?.lectures[0]?.title ?? "강의 학습" : "오늘의 학습"}</h1></div>
      <nav><Link to="/study">전체 학습</Link><Link to="/">캘린더</Link><Link to="/guide#learning">학습 방법</Link>{subject ? <Link to={legacy}>기존 풀이</Link> : null}</nav></header>
    {error ? <p role="alert" className="notice is-error">{error} <button onClick={() => void run(load)}>다시 불러오기</button></p> : null}
    {sid && session ? <LearningRun key={session.sessionId} session={session} busy={busy}
      act={(action, body) => void run(() => mutation(action, body))} home={() => setParams({})} /> : sid ? <p>학습을 불러오는 중…</p> : dashboard ? <>
      <WorkloadSummary dashboard={dashboard} />
      <p className="learning-muted">공부한 범위는 정답·해설을 확인하고 평가한 수예요. 설명만 있는 내용은 확인한 뒤 포함합니다.
        {dashboard.missingLectures.length ? ` 자료 미준비 ${dashboard.missingLectures.length}강의는 위 숫자에 포함되지 않아요.` : ""}</p>
      <section className="learning-plan">
        <div><span className="learning-eyebrow">오늘의 약속</span><h2>{timeLimitReached ? "오늘 공부 시간을 채웠어요" : dashboard.plan.complete ? "오늘 계획을 마쳤어요" : `${Math.round(dashboard.plan.budgetSeconds / 60)}분 안에서 한 걸음씩`}</h2>
          <p>전체 계획 {dashboard.plan.completed.length} / {dashboard.plan.entries.length}개 활동 완료 · {fmt(dashboard.plan.activeSeconds)} 학습</p>
          <progress aria-label="오늘 활동 완료" max={Math.max(1, dashboard.plan.entries.length)} value={dashboard.plan.completed.length} /></div>
        <p className="learning-start-hint">{dashboard.activeSession ? "진행 중인 학습을 이어가세요. 마친 뒤 다음 공부를 선택할 수 있어요."
          : timeLimitReached ? "미완료 분량은 남아 있어요. 남은 계획을 조정하거나 추가 학습으로 이어갈 수 있어요."
          : dashboard.plan.complete ? "오늘 분량은 끝났어요. 더 공부하거나 시험 연습으로 확인할 수 있어요."
          : dashboard.plan.remaining > 0 ? "처음이라면 ‘오늘 학습 시작’을 누르세요. 새 내용과 복습을 순서대로 안내합니다."
          : "이 강의를 더 공부하려면 추가 학습을, 오늘 배정된 분량을 보려면 전체 학습을 선택하세요."}</p>
        <div className="learning-actions">
          {dashboard.activeSession ? <button className="primary" onClick={() => setParams({ session: dashboard.activeSession! })}>진행 중 학습 이어가기</button> : null}
          {!dashboard.plan.complete && dashboard.plan.remaining > 0 ? <button className="primary" disabled={busy || !dashboard.enabled} onClick={() => void start("daily")}>오늘 학습 시작 · {dashboard.plan.remaining}개 활동</button> : null}
        </div>
        <div className="learning-optional-modes">
          <div><button disabled={busy || !dashboard.enabled || !dashboard.progress.total} onClick={() => void start("extra")}>추가 학습 · 더 공부하기</button><p>오늘 분량과 별도로 더 공부해요. 중간에 마쳐도 됩니다.</p></div>
          <div><button disabled={busy || !dashboard.enabled || dashboard.examQuestions === 0} onClick={() => void start("exam")}>시험 연습 · 처음 보는 객관식</button><p>배운 범위에서 아직 안 본 시험 문제가 있는 {dashboard.examQuestions}개 요점으로 실력을 확인해요.</p></div>
        </div>
        {subject && !dashboard.plan.remaining && !dashboard.plan.complete ? <p>이 강의는 오늘 배정된 활동이 없습니다. <Link to="/study">전체 계획</Link>에서 이어가거나 추가 학습을 선택하세요.</p> : null}
        {dashboard.examQuestions === 0 ? <p className="learning-muted">배운 범위에 아직 보지 않은 시험용 객관식이 준비되면 시험 연습을 시작할 수 있습니다.</p> : null}
        {dashboard.plan.infeasible ? <p className="learning-warning">첫 회독 목표일까지 새 범위에 하루 약 {dashboard.plan.newRequiredMinutes}분이 필요합니다. 가용시간이나 첫 회독 여유일을 조정해 주세요.</p> : null}
      </section>
      <LectureWorkload lectures={dashboard.lectures} scoped={Boolean(subject)} />
      <details className="learning-panel"><summary>기억 확인과 자료 준비 현황</summary>
        <p>시간을 두고 기억한 요점 {dashboard.progress.delayedRecall}개 · 학습 문제 준비 중 {dashboard.progress.questionGaps}개</p>
        <p className="learning-muted">기억한 요점은 자동채점 문항을 간격을 두고 두 번, 도움이나 찍음 없이 맞힌 수예요.</p></details>
      <LearningOverview />
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
  const explanationOnly = value.correct === undefined && value.answer === undefined;
  const explanations = value.optionExplanations ?? [];
  const distractor = explanations.find(e => !value.correctOptionIds?.includes(e.option_id)
    && picked.includes(e.option_id)) ?? explanations.find(e => !value.correctOptionIds?.includes(e.option_id));
  const focused = explanations.filter(e => value.correctOptionIds?.includes(e.option_id)
    || picked.includes(e.option_id) || e === distractor);
  return <section className="learning-feedback" aria-label={explanationOnly ? "학습 설명" : "정답과 해설"}>
    <h3>{explanationOnly ? "학습 설명" : "정답과 해설"}</h3>
    {value.correct !== undefined && value.correct !== null ? <p className="learning-verdict">{value.correct ? "맞았습니다" : "차이를 확인해 볼까요"}{value.confidence === "guess" ? " · 찍은 답은 다시 확인합니다" : ""}</p> : null}
    {value.correct === false && value.confidence === "sure" ? <p>확신했던 답과 정답이 갈리는 조건을 확인하세요. 내가 고른 선지의 해설부터 비교해 보세요.</p> : null}
    {value.correct === true && value.confidence === "unsure" ? <p>헷갈렸어도 스스로 맞혔다면 기억 성공입니다. 답을 고른 근거를 해설과 비교해 보세요.</p> : null}
    {value.answer ? <p><Stem text={value.answer} /></p> : null}
    {focused.map(e => <p key={e.option_id}><b>{e.option_id}</b> <Stem text={e.text} /></p>)}
    {!explanations.length && value.answerUnits?.length ? <ul>{value.answerUnits.map((a, i) => <li key={i}><Stem text={a} /></li>)}</ul> : null}
    {value.answerPairs?.length ? <ul>{value.answerPairs.map((p, i) => <li key={i}>{p.left} → {p.right}</li>)}</ul> : null}
    {value.correctOrder?.length ? <p>{value.correctOrder.join(" → ")}</p> : null}
    {explanations.length > focused.length ? <details><summary>모든 선지 해설</summary>{explanations.map(e => <p key={e.option_id}><b>{e.option_id}</b> <Stem text={e.text} /></p>)}</details> : null}
    {value.explanation ? explanationOnly ? <><p><Stem text={value.explanation} /></p><p><b>기억할 내용</b> <Stem text={value.minimum} /></p></>
      : <details><summary>맥락과 설명</summary><p><Stem text={value.explanation} /></p><p><b>기억할 내용</b> <Stem text={value.minimum} /></p></details> : null}
    {value.sourceConflict ? <p className="learning-warning">자료 충돌: {value.sourceConflict}</p> : null}
    {value.medicalReview && value.medicalReview.verdict !== "ok" ? <p className="learning-warning">정답 검토 · {value.medicalReview.note}<br />{value.medicalReview.suggested_answer}</p> : null}
    <SourceRefs refs={value.sourceRefs} />
  </section>;
}

function LearningRun({ session: s, busy, act, home }: { session: LearningSession; busy: boolean;
  act: (action: string, body: object) => void; home: () => void }) {
  const [answer, setAnswer] = useState<LearningAnswer>({});
  const [confidence, setConfidence] = useState<"sure" | "unsure" | "guess" | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const seconds = useRef(0);
  const answerRef = useRef(answer);
  answerRef.current = answer;
  const draftKey = `studyez-learning-${s.sessionId}`;
  const q = s.question;
  useEffect(() => {
    let draft: { token?: string; seconds?: number; answer?: LearningAnswer; confidence?: "sure" | "unsure" | "guess" | null } = {};
    try { draft = JSON.parse(sessionStorage.getItem(draftKey) || "{}"); } catch { /* Storage is optional. */ }
    const resumed = draft.token === s.token;
    setAnswer(s.submittedAnswer ?? (resumed ? draft.answer : null) ?? { order: q ? shuffled(q.sequence_items, s.token ?? "") : [] });
    setConfidence(resumed ? draft.confidence ?? null : null);
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
  const ack = (selfCorrect?: boolean, reviewRating?: RecallRating) => act("acknowledge", { token: s.token, selfCorrect, reviewRating, activeSeconds: Math.floor(seconds.current) });
  useEffect(() => {
    if (!s.token) return;
    try { const draft = JSON.parse(sessionStorage.getItem(draftKey) || "{}");
      sessionStorage.setItem(draftKey, JSON.stringify({ ...draft, token: s.token, confidence }));
    } catch { /* Storage is optional. */ }
  }, [confidence, s.token]);
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
  const textRecall = Boolean(q && ["basic", "cloze", "list"].includes(q.format));
  const selfCheck = Boolean(s.submitted && q && s.feedback?.correct == null && s.mode !== "exam");
  const answerTask = q?.format === "matching" ? "짝 연결하기" : q?.format === "sequence" ? "순서 맞추기" : "답 선택하기";
  const steps = s.mode === "exam" ? ["답 선택하기", "답 저장", "다음 문제로"]
    : [textRecall || showRecall ? "답 떠올리기" : q ? answerTask : "요점 살펴보기", q ? "정답·해설 확인" : "설명 보기", q ? "기억 평가 · 다음 복습" : "확인하고 다음으로"];
  return <>
    <div className="learning-run-bar"><span>{LANES[s.lane ?? ""]} · 이번 학습 {s.index + 1} / {s.total}개 활동</span><span>이 활동 {fmt(elapsed)}</span></div>
    {s.mode === "extra" ? <p className="learning-muted">오늘 분량과 별도로 더 공부하는 중이에요. 원하는 때 ‘여기서 마치기’를 눌러도 됩니다.</p> : null}
    {s.mode !== "exam" ? <p className="learning-context">{s.lecture}</p> : null}
    <article className="learning-question">
      <ol className="learning-question-steps" aria-label="이 문항의 학습 순서">{steps.map((step, index) => <li key={index} aria-current={index === (s.submitted ? 2 : 0) ? "step" : undefined}><span aria-hidden="true">{index + 1}</span>{step}</li>)}</ol>
      <h2><Stem text={promptText(showRecall ? s.recallPrompt! : q?.question ?? s.objective ?? "설명 학습")} /></h2>
      {!s.submitted ? <p className="learning-instruction">{s.mode === "exam" ? "답을 고르고 저장하세요. 정답과 해설은 시험 연습을 마친 뒤 공개됩니다."
        : showRecall ? "먼저 답을 잠깐 떠올려 보세요. 생각이 안 나면 바로 보기를 펼쳐도 됩니다."
        : textRecall ? "머릿속으로 답을 떠올린 뒤 정답을 확인하세요. 떠오르지 않아도 확인하고 다음으로 넘어갈 수 있어요."
        : q?.format === "matching" ? "각 항목의 짝을 연결한 뒤 정답을 확인하세요."
        : q?.format === "sequence" ? "화살표로 순서를 맞춘 뒤 정답을 확인하세요."
        : q ? "답을 선택한 뒤 정답과 해설을 확인하세요."
        : "학습요점을 살펴보고 아래의 ‘설명 보기’를 눌러 기억할 내용을 확인하세요."}</p> : null}
      {showRecall ? <button disabled={busy} onClick={() => act("action", { token: s.token, action: "options" })}>보기 펼치기</button> : null}
      {q?.options.length ? <div className="learning-options">{q.options.map(o => <button key={o.id} aria-pressed={picked.includes(o.id)} disabled={busy || s.submitted} onClick={() => choose(o.id)}><b>{o.id}</b><Stem text={o.text} /></button>)}</div> : null}
      {q?.format === "ox" ? <div className="learning-actions">{["O", "X"].map(v => <button key={v} disabled={busy || s.submitted} aria-pressed={answer.text === v} onClick={() => setAnswer({ text: v })}>{v}</button>)}</div> : null}
      {q?.format === "matching" ? <div className="learning-matching">{q.matching_left.map(l => <label key={l}>{l}<select aria-label={`${l}의 짝`} disabled={busy || s.submitted} value={answer.pairs?.[l] ?? ""} onChange={e => setAnswer({ pairs: { ...answer.pairs, [l]: e.target.value } })}><option value="">선택</option>{shuffled(q.matching_right, s.token ?? "").map(r => <option key={r}>{r}</option>)}</select></label>)}</div> : null}
      {q?.format === "sequence" ? <ol>{(answer.order ?? []).map((item, i) => <li key={item} className="learning-sequence">{item}<button disabled={busy || s.submitted || i === 0} aria-label={`${item} 위로`} onClick={() => {
        const order = [...(answer.order ?? [])]; [order[i - 1], order[i]] = [order[i], order[i - 1]]; setAnswer({ order });
      }}>↑</button></li>)}</ol> : null}
      {textRecall && !s.submitted ? <label className="learning-recall">떠올린 답 메모 (선택)<small>메모는 자동채점하지 않아요. 정답을 본 뒤 떠올린 내용과 직접 비교합니다.</small><textarea value={answer.text ?? ""} onChange={e => setAnswer({ text: e.target.value })} placeholder="적지 않고 머릿속으로만 답해도 돼요" /></label> : null}
      {s.mode !== "exam" && !s.submitted && !s.help ? <div className="learning-actions learning-help-actions"><button disabled={busy} onClick={() => act("action", { token: s.token, action: "help" })}>막혔나요? 설명·기억할 내용 보기</button></div> : null}
      {s.help ? <aside className="learning-help"><h3>이해 설명과 기억할 내용</h3><p>{s.help.context}</p><p><Stem text={s.help.explanation || "이 기존 문항에는 별도의 이해 설명이 없습니다. 정답과 원본을 확인한 뒤 다음 범위로 넘어갈 수 있습니다."} /></p><p><b>기억할 내용</b> <Stem text={s.help.minimum} /></p><p className="learning-muted">{s.help.rationale}</p><SourceRefs refs={s.help.source_refs} /></aside> : null}
      {s.assisted ? <p className="learning-muted">도움을 받은 학습으로 기록합니다. 다음에는 도움 없이 확인합니다.</p> : null}
      {selfCheck && answer.text?.trim() ? <aside className="learning-answer-memo"><h3>내가 떠올린 답</h3><p>{answer.text}</p></aside> : null}
      {s.feedback ? <Feedback value={s.feedback} picked={picked} /> : null}
      {s.subject && s.runId && (s.feedback || s.help) ? <p><Link target="_blank" to={`/lectures/${encodeURIComponent(s.subject)}/${encodeURIComponent(s.runId)}`}>원본 강의 자료 열기 ↗</Link></p> : null}
    </article>
    <footer className="learning-controls">
      {!s.submitted && !showRecall ? <>{q ? <details><summary>답할 때의 확신 기록 (선택)</summary><p>정답을 보기 전의 상태를 남겨요. 헷갈려도 스스로 맞혔다면 실패로 처리하지 않습니다.</p><div className="learning-actions learning-confidence-actions">
        {([["sure", "확실해요"], ["unsure", "헷갈려요"], ["guess", textRecall ? "모르겠어요" : "찍었어요"]] as const).map(([value, label]) => <button disabled={busy} aria-pressed={confidence === value} key={value} onClick={() => setConfidence(confidence === value ? null : value)}>{label}</button>)}
      </div></details> : null}<div className="learning-actions"><button className="primary" disabled={busy || !ready} onClick={() => act("submit", { token: s.token, confidence, answer: q ? answer : {}, activeSeconds: Math.floor(seconds.current) })}>{q ? s.mode === "exam" ? "답변 저장" : "정답 보기" : "설명 보기"}</button></div></> : null}
      {s.submitted ? <><p>{selfCheck ? "정답과 떠올린 답을 비교하고, 정답을 보기 전에 실제로 기억했던 정도로 평가하세요."
        : s.mode === "exam" ? "답변을 저장했어요. 다음 문제로 넘어가세요. 정답은 연습을 마친 뒤 확인합니다."
        : q ? "해설을 확인하고, 답할 때 실제로 기억한 정도를 평가하세요. 오답·찍음·도움을 받은 답은 ‘다시’입니다." : "설명을 확인했으면 다음으로 넘어가세요."}</p>
        {q && s.mode !== "exam" && s.reviewChoices ? <><p className="learning-muted">버튼에 표시된 간격으로 다음 복습을 잡아요. 어렵게 맞힌 답도 기억 성공입니다.</p><div className="learning-actions">{s.reviewChoices.map(choice => <button disabled={busy} key={choice.rating} onClick={() => ack(selfCheck ? choice.rating !== "Again" : undefined, choice.rating)}>{RATING_LABELS[choice.rating]} · {Math.round(choice.intervalDays)}일 뒤</button>)}</div></>
          : <div className="learning-actions">{selfCheck ? <><button disabled={busy} onClick={() => ack(false)}>기억하지 못했어요 · 다음</button><button className="primary" disabled={busy} onClick={() => ack(true)}>스스로 맞혔어요 · 다음</button></> : <button className="primary" disabled={busy} onClick={() => ack()}>{s.mode === "exam" ? "다음 문제로" : "확인했어요 · 다음"}</button>}</div>}</> : null}
      <div className="learning-actions">{s.canUndo && !s.submitted ? <button disabled={busy} onClick={() => act("undo", {})}>이전 평가 되돌리기</button> : null}<button disabled={busy} onClick={() => act("end", { token: s.token, activeSeconds: Math.floor(seconds.current) })}>여기서 마치기</button></div>
    </footer>
  </>;
}
