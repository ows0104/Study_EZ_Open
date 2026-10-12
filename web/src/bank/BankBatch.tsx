import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { takeTimetable } from "../firstScreen";
import { useMe } from "../useMe";
import type { LectureRef, TimetableEvent } from "../types/lectures";
import type { BankNext, BankSession } from "../types/bank";
import { BankSolve, type BatchStudy } from "./BankSolve";
import { useBankUndo } from "./useBankUndo";
import "./batch.css";

type Lecture = Pick<LectureRef, "subject" | "runId" | "title"> & { date: string };
type Queue = { lectures: Lecture[]; current?: Lecture; undoToken?: string | null; goal?: BankNext["batchGoal"] };
const keyOf = (lecture: Lecture) => `${lecture.subject}/${lecture.runId}`;

/** 문항마다 서버가 고른 강의로 바뀐다. 기록과 복습 일정은 강의별로 유지한다. */
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
        && saved.lectures.every(l => typeof l.subject === "string" && typeof l.runId === "string"
          && typeof l.title === "string" && typeof l.date === "string") ? saved : null;
    } catch { return null; }
  });
  const [done, setDone] = useState(false);
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState("");
  const [auditing, setAuditing] = useState(false);
  const [auditMessage, setAuditMessage] = useState("");
  const current = queue?.current ?? queue?.lectures[0];
  const progress = useCallback((got: BankNext) => {
    setQueue(old => old ? { ...old, current: got.lecture ? old.lectures.find(l => keyOf(l) === `${got.lecture!.subject}/${got.lecture!.runId}`) : old.current,
      undoToken: got.undoToken, goal: got.batchGoal } : old);
  }, []);
  const batch = useMemo<BatchStudy | undefined>(() => queue ? { lectures: queue.lectures, resumeLecture: queue.current, onProgress: progress } : undefined,
    [queue?.lectures, progress]);
  const requestUndo = useCallback((token: string) => api<BankNext>("/api/bank/batch/undo", {
    method: "POST", body: JSON.stringify({ lectures: queue?.lectures, reviewToken: token }),
  }), [queue?.lectures]);
  const restore = useCallback((got: BankNext) => { progress(got); setDone(false); setPaused(false); }, [progress]);
  const { undo, undoBusy } = useBankUndo("/api/bank/batch", queue?.undoToken, restore, setError, !done && !paused, requestUndo);

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

  const finished = useCallback((summary: BankSession | null) => {
    if (summary?.reason === "user_finished") setPaused(true);
    else setDone(true);
  }, []);
  const visible = useMemo(() => (lectures ?? []).filter(l => (!subject || l.subject === subject)
    && `${l.title} ${l.date}`.toLowerCase().includes(search.toLowerCase())), [lectures, subject, search]);

  if (queue) return <>
    <div className="batch-progress" role="status">
      <span>강의 모아 풀기</span>
      <strong>{queue.lectures.length}강의 섞어 풀기{!done && current ? ` · ${current.title}` : ""}</strong>
      <button className="is-quiet" onClick={() => { setQueue(null); setDone(false); setPaused(false); setError(""); }}>강의 다시 선택</button>
    </div>
    {error ? <p role="alert" className="notice is-error">{error}</p> : null}
    {current && !done && !paused ? <BankSolve base="" lecture={current} onFinished={finished} batch={batch} />
      : <div className="quiz bank-start">
        <h2>{paused ? "모아 풀기를 쉬고 있어요" : "새 카드와 오늘 복습을 모두 마쳤어요"}</h2>
        <p>{paused ? "평가한 카드는 저장됐습니다. 이어서 풀면 남은 문제를 섞어서 계속합니다."
          : "선택한 강의의 새 카드와 예정된 복습을 모두 평가했습니다."}</p>
        {paused ? <button onClick={() => setPaused(false)}>이어서 학습</button> : null}{" "}
        {queue.undoToken ? <button disabled={undoBusy} onClick={() => void undo()}>마지막 평가 되돌리기 <kbd>Z</kbd></button> : null}{" "}
        <Link to="/">캘린더로</Link>
      </div>}
  </>;

  return <section className="batch-picker">
    <h1>강의 모아 풀기</h1>
    <p>선택한 강의의 문제를 섞어서 풉니다. 새 카드를 먼저 보고 예정된 복습까지 모두 하면 완료됩니다.</p>
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
        if (chosen.length) { setPaused(false); setDone(false); setQueue({ lectures: chosen }); }
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
