import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { invalidateTimetable } from "../firstScreen";
import { LearningOverview } from "./LearningOverview";
import { LectureWorkload, WorkloadSummary } from "./LearningWorkload";
import { LearningRun } from "./LearningRun";
import { SourceRefs } from "./LearningFeedback";
import type { LearningDashboard, LearningSession } from "../types/learning";
import "../styles/learning.css";

const ROOT = "/api/learning";

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
  return <section className={`learning${sid ? " is-studying" : ""}`}>
    <header className="learning-header"><div><span className="learning-eyebrow">Study EZ{subject ? " · 강의 학습" : ""}</span><h1>{session?.mode === "exam" ? "시험 연습" : session ? session.lecture ?? "강의 학습" : subject ? dashboard?.lectures[0]?.title ?? "강의 학습" : "오늘 학습"}</h1></div>
      {!sid ? <nav><Link to="/study">전체 학습</Link><Link to="/">캘린더</Link><Link to="/guide#learning">학습 방법</Link>{subject ? <Link to={legacy}>기존 풀이</Link> : null}</nav> : null}</header>
    {error ? <p role="alert" className="notice is-error">{error} <button onClick={() => void run(load)}>다시 불러오기</button></p> : null}
    {sid && session ? <LearningRun key={session.sessionId} session={session} busy={busy}
      act={(action, body) => void run(() => mutation(action, body))} home={() => setParams({})} /> : sid ? <p>학습을 불러오는 중…</p> : dashboard ? <>
      <WorkloadSummary dashboard={dashboard} />
      <section className="learning-plan learning-start">
        <h2>{dashboard.activeSession ? "이어서 공부하기" : timeLimitReached ? "오늘 공부 시간 완료" : dashboard.plan.complete ? "오늘 분량 완료" : "학습 시작"}</h2>
        <div className="learning-actions">
          {dashboard.activeSession ? <button className="primary" onClick={() => setParams({ session: dashboard.activeSession! })}>학습 이어가기</button> : null}
          {!dashboard.activeSession && !dashboard.plan.complete && dashboard.plan.remaining > 0 ? <button className="primary" disabled={busy || !dashboard.enabled} onClick={() => void start("daily")}>오늘 학습 시작</button> : null}
        </div>
        <div className="learning-optional-modes">
          <div><button disabled={busy || Boolean(dashboard.activeSession) || !dashboard.enabled || !dashboard.progress.total} onClick={() => void start("extra")}>추가 학습</button><p>원하는 강의를 더 공부하기</p></div>
          <div><button disabled={busy || Boolean(dashboard.activeSession) || !dashboard.enabled || dashboard.examQuestions === 0} onClick={() => void start("exam")}>시험 연습</button><p>배운 범위의 새 문제 · {dashboard.examQuestions}개 요점</p></div>
        </div>
        {subject && !dashboard.plan.remaining && !dashboard.plan.complete ? <p>이 강의는 오늘 배정된 활동이 없습니다. <Link to="/study">전체 계획</Link>에서 이어가거나 추가 학습을 선택하세요.</p> : null}

        {dashboard.plan.infeasible ? <p className="learning-warning">전체 강의의 첫 회독 목표일까지 새 범위에 하루 약 {dashboard.plan.newRequiredMinutes}분이 필요합니다. 모든 강의가 하루 공부 시간을 함께 사용해요. 가용시간이나 첫 회독 여유일을 조정해 주세요.</p> : null}
      </section>
      <LectureWorkload lectures={dashboard.lectures} scoped={Boolean(subject)} />
      <details className="learning-panel"><summary>기억 확인과 자료 준비 현황</summary>
        <p>시간을 두고 기억한 요점 {dashboard.progress.delayedRecall}개 · 학습 문제 준비 중 {dashboard.progress.questionGaps}개</p>
        <p className="learning-muted">기억한 요점은 자동채점 문항을 간격을 두고 두 번, 도움이나 찍음 없이 맞힌 수예요.</p></details>
      <details className="learning-panel"><summary>학습 방법</summary><LearningOverview /></details>
      <details className="learning-panel"><summary>학습량 집계 기준</summary><p>정답·해설을 확인하고 평가한 범위를 셉니다. 반복·변형은 첫 회독 수를 늘리지 않아요.</p><p>기존 자료는 문항별로 집계합니다. 미준비 강의는 전체 수에 포함하지 않으며, 과거 자기평가는 정답률로 환산하지 않습니다.</p></details>
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
