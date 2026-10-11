import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { invalidateTimetable } from "../firstScreen";
import { LearningDashboard as Dashboard } from "./LearningDashboard";
import { LearningRun } from "./LearningRun";
import type { LearningDashboard, LearningSession } from "../types/learning";
import "../styles/learning.css";

const ROOT = "/api/learning";

export function LearningPage() {
  const { subject, runId } = useParams();
  const [params, setParams] = useSearchParams();
  const sid = params.get("session");
  const [dashboard, setDashboard] = useState<LearningDashboard | null>(null);
  const [session, setSession] = useState<LearningSession | null>(null);
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
      setDashboard(info);
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
  return <section className={`learning${sid ? " is-studying" : ""}`}>
    <header className="learning-header"><div><span className="learning-eyebrow">{subject ?? "Study EZ"}</span><h1>{session?.mode === "exam" ? "시험 연습" : session ? session.lecture ?? "강의 학습" : subject ? dashboard?.lectures[0]?.title ?? dashboard?.scopeOnlyLectures?.[0]?.title ?? "강의 학습" : "오늘 학습"}</h1></div>
      {!sid && subject ? <nav><Link to="/study">← 전체 강의</Link></nav> : null}</header>
    {error ? <p role="alert" className="notice is-error">{error} <button onClick={() => void run(load)}>다시 불러오기</button></p> : null}
    {sid && session ? <LearningRun key={session.sessionId} session={session} busy={busy}
      act={(action, body) => void run(() => mutation(action, body))} home={() => setParams({})} /> : sid ? <p>학습을 불러오는 중…</p> : dashboard ? <Dashboard key={scopeQuery} dashboard={dashboard} scoped={Boolean(subject && runId)} subject={subject} runId={runId} busy={busy}
      start={mode => void start(mode)} resume={() => setParams({ session: dashboard.activeSession! })}
      saveSettings={(minutes, buffer, replan) => void run(async () => {
        await api(`${ROOT}/settings`, { method: "PUT", body: JSON.stringify({ minutes, bufferDays: buffer, enabled: true, replan }) }); await load();
      })} /> : <p>학습 계획을 준비하는 중…</p>}
  </section>;
}
