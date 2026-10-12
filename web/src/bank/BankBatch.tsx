import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { takeTimetable } from "../firstScreen";
import { useMe } from "../useMe";
import type { LectureRef, TimetableEvent } from "../types/lectures";
import type { BankRead, BankSession } from "../types/bank";
import { BankSolve } from "./BankSolve";
import "./batch.css";

type Lecture = Pick<LectureRef, "subject" | "runId" | "title"> & { date: string };
type Queue = { lectures: Lecture[]; index: number; skipped?: number };
const keyOf = (lecture: Lecture) => `${lecture.subject}/${lecture.runId}`;
const baseOf = (lecture: Lecture) => `/api/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}/bank`;

/** 기존 강의별 회차와 기록을 그대로 쓰고, 완료하면 다음 강의를 연다. */
export function BankBatchPage() {
  const me = useMe();
  const storageKey = `studyez-batch:${me?.id ?? ""}`;
  const [lectures, setLectures] = useState<Lecture[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [subject, setSubject] = useState("");
  const [search, setSearch] = useState("");
  const [queue, setQueue] = useState<Queue | null>(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) ?? "null") as Queue | null;
      return saved && Array.isArray(saved.lectures) && saved.lectures.length > 0
        && Number.isInteger(saved.index) && saved.index >= 0 && saved.index <= saved.lectures.length
        && saved.lectures.every(l => typeof l.subject === "string" && typeof l.runId === "string"
          && typeof l.title === "string" && typeof l.date === "string") ? saved : null;
    } catch { return null; }
  });
  const [solving, setSolving] = useState(false);
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [auditing, setAuditing] = useState(false);
  const [auditMessage, setAuditMessage] = useState("");
  const current = queue?.lectures[queue.index];

  useEffect(() => {
    document.title = "강의 모아 풀기 · Study_EZ";
    let live = true;
    takeTimetable().then(data => {
      const unique = new Map<string, Lecture>();
      data.events.forEach((event: TimetableEvent) => event.lectures.filter(l => l.marks.quiz).forEach(l => {
        const row = { subject: l.subject, runId: l.runId, title: l.title, date: event.date };
        unique.set(keyOf(row), row);
      }));
      if (live) setLectures([...unique.values()].sort((a, b) => a.date.localeCompare(b.date) || a.runId.localeCompare(b.runId)));
    }).catch((cause: Error) => { if (live) setError(cause.message); });
    return () => { live = false; };
  }, []);
  useEffect(() => {
    try {
      if (queue) sessionStorage.setItem(storageKey, JSON.stringify(queue));
      else sessionStorage.removeItem(storageKey);
    } catch { /* 브라우저 저장을 막아도 현재 탭에서는 학습한다. */ }
  }, [queue, storageKey]);

  useEffect(() => {
    if (!current || paused) return;
    let live = true;
    setSolving(false);
    setError("");
    (async () => {
      const base = baseOf(current);
      const info = await api<BankRead>(base);
      if (!live) return;
      if (!info.summary.usable) throw new Error(`${current.title}: 지금 학습할 수 없는 강의입니다.`);
      if (info.lectureGoal?.met) {
        setQueue(old => old ? { ...old, index: old.index + 1 } : null);
        return;
      }
      await api(`${base}/session/start`, { method: "POST", body: JSON.stringify({ size: null, dailyOnly: true }) });
      if (live) setSolving(true);
    })().catch((cause: Error) => { if (live) setError(cause.message); });
    return () => { live = false; };
  }, [current, paused, reload]);

  const finished = useCallback((summary: BankSession | null) => {
    setSolving(false);
    if (summary?.reason === "user_finished") setPaused(true);
    else setQueue(old => old ? { ...old, index: old.index + 1 } : null);
  }, []);
  const visible = useMemo(() => (lectures ?? []).filter(l => (!subject || l.subject === subject)
    && `${l.title} ${l.date}`.toLowerCase().includes(search.toLowerCase())), [lectures, subject, search]);

  if (queue) return <>
    <div className="batch-progress" role="status">
      <span>강의 모아 풀기</span>
      <strong>{current ? `${queue.index + 1} / ${queue.lectures.length}강의 · ${current.title}` : "선택한 강의 학습 종료"}</strong>
      {current ? <span>{current.subject} · {current.date}</span> : null}
    </div>
    {error ? <div className="quiz bank-start"><p role="alert" className="notice is-error">{error}</p>
      <button onClick={() => setReload(n => n + 1)}>다시 시도</button>{" "}
      <button className="is-quiet" onClick={() => { setPaused(false); setError(""); setQueue(old => old ? { ...old, index: old.index + 1, skipped: (old.skipped ?? 0) + 1 } : null); }}>이 강의 건너뛰기</button>
    </div> : current && solving ? <BankSolve key={keyOf(current)} base={baseOf(current)} lecture={current} onFinished={finished} />
      : current && !paused ? <p className="notice">강의를 여는 중…</p> : <div className="quiz bank-start">
        <h2>{paused ? "모아 풀기를 쉬고 있어요" : queue.skipped ? "모아 풀기를 마쳤어요" : "선택한 강의의 오늘 분량을 마쳤어요"}</h2>
        <p>{paused ? "평가한 카드는 저장됐습니다. 이어서 풀면 남은 새 카드부터 계속합니다." : queue.skipped
          ? `직접 건너뛴 강의 ${queue.skipped}개에는 남은 분량이 있을 수 있습니다. 다시 선택해서 이어 풀 수 있습니다.`
          : "강의마다 새 카드를 먼저 보고 예정된 복습까지 진행했습니다. 오늘 분량을 이미 마친 강의는 건너뛰었습니다."}</p>
        {paused ? <button onClick={() => setPaused(false)}>이어서 학습</button> : null}{" "}
        <button className="is-quiet" onClick={() => { setQueue(null); setPaused(false); }}>강의 다시 선택</button>{" "}
        <Link to="/">캘린더로</Link>
      </div>}
  </>;

  return <section className="batch-picker">
    <h1>강의 모아 풀기</h1>
    <p>강의를 고르면 날짜순으로 이어서 풉니다. 한 강의의 새 카드 → 예정된 복습 → 다음 강의 순서입니다.</p>
    <div className="batch-filters">
      <label>과목 <select value={subject} onChange={e => setSubject(e.target.value)}>
        <option value="">모든 과목</option>
        {[...new Set((lectures ?? []).map(l => l.subject))].map(s => <option key={s}>{s}</option>)}
      </select></label>
      <label>강의 검색 <input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="강의명 또는 날짜" /></label>
    </div>
    <div className="batch-actions">
      <button className="is-quiet" onClick={() => setSelected(old => new Set([...old, ...visible.map(keyOf)]))}>표시된 강의 모두 선택</button>
      <button className="is-quiet" onClick={() => setSelected(new Set())}>선택 해제</button>
      <button disabled={!selected.size} onClick={() => {
        const chosen = (lectures ?? []).filter(l => selected.has(keyOf(l)));
        if (chosen.length) { setPaused(false); setQueue({ lectures: chosen, index: 0 }); }
      }}>{selected.size}강의 학습 시작</button>
      {me?.isAdmin ? <button className="is-quiet" disabled={!selected.size || auditing} onClick={() => void (async () => {
        setAuditing(true); setAuditMessage("");
        const failures: string[] = [];
        let requested = 0;
        for (const lecture of (lectures ?? []).filter(l => selected.has(keyOf(l)))) {
          try {
            await api(`/api/admin/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}/bank/audit`, { method: "POST" });
            requested++;
          } catch (cause) { failures.push(`${lecture.title}: ${(cause as Error).message}`); }
        }
        setAuditMessage(`${requested}강의 검증·보강 요청 완료${failures.length ? ` · 요청 실패 ${failures.join(" / ")}` : " · 러너가 처리합니다. 기존 카드로 계속 공부할 수 있습니다."}`);
        setAuditing(false);
      })()}>{auditing ? "요청 중…" : "선택 강의 누락 검증·객관식 보강"}</button> : null}
    </div>
    {auditMessage ? <p role="status" className="bank-note">{auditMessage}</p> : null}
    {error ? <p className="notice is-error" role="alert">{error}</p> : null}
    {!lectures ? <p className="notice">강의를 불러오는 중…</p> : !visible.length ? <p>학습 가능한 강의가 없습니다.</p> : <ul className="batch-lectures">
      {visible.map(l => <li key={keyOf(l)}><label>
        <input type="checkbox" checked={selected.has(keyOf(l))} onChange={e => {
          const checked = e.target.checked;
          setSelected(old => { const next = new Set(old); if (checked) next.add(keyOf(l)); else next.delete(keyOf(l)); return next; });
        }} />
        <span><strong>{l.title}</strong><small>{l.date} · {l.subject}</small></span>
      </label></li>)}
    </ul>}
  </section>;
}
