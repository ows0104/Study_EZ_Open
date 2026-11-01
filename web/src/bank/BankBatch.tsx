import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useMe } from "../useMe";
import type { BankNext, BankSession } from "../types/bank";
import { StudyOverview, type StudyLecture } from "./StudyOverview";
import { DeleteQuizDialog } from "./DeleteQuizDialog";
import { BankSolve, type BatchStudy } from "./BankSolve";
import { useBankUndo } from "./useBankUndo";
import { useStudyTimetable } from "./useStudyTimetable";
import "./batch.css";

type Lecture = Pick<StudyLecture, "subject" | "runId" | "title" | "date">;
type Queue = { lectures: Lecture[]; current?: Lecture; undoToken?: string | null; goal?: BankNext["batchGoal"] };
const keyOf = (lecture: Lecture) => `${lecture.subject}/${lecture.runId}`;

/** 문항마다 서버가 고른 강의로 바뀐다. 기록과 복습 일정은 강의별로 유지한다. */
export function BankBatchPage() {
  const me = useMe();
  const storageKey = `studyez-batch:${me?.id ?? ""}`;
  const [hiddenKeys, setHiddenKeys] = useState<string[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [managing, setManaging] = useState(false);
  const [manageMessage, setManageMessage] = useState("");
  const [deleting, setDeleting] = useState<StudyLecture[] | null>(null);
  const requestVersion = useRef(0);
  const [queue, setQueue] = useState<Queue | null>(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) ?? "null") as Queue | null;
      return saved && Array.isArray(saved.lectures) && saved.lectures.length > 0
        && saved.lectures.every(l => typeof l.subject === "string" && typeof l.runId === "string"
          && typeof l.title === "string" && typeof l.date === "string") ? saved : null;
    } catch { return null; }
  });
  const [done, setDone] = useState(false);
  const { events, setEvents, onScope, error: loadError } = useStudyTimetable(refreshKey, !queue);
  const [paused, setPaused] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [auditing, setAuditing] = useState(false);
  const [auditMessage, setAuditMessage] = useState("");
  const current = queue?.current ?? queue?.lectures[0];
  const progress = useCallback((got: BankNext) => {
    setQueue(old => old ? { ...old, current: got.lecture ? old.lectures.find(l => keyOf(l) === `${got.lecture!.subject}/${got.lecture!.runId}`) : old.current,
      undoToken: got.undoToken, goal: got.batchGoal } : old);
  }, []);
  const batch = useMemo<BatchStudy | undefined>(() => queue ? { lectures: queue.lectures, resumeLecture: queue.current, onProgress: progress, onSavingChange: setSaving } : undefined,
    [queue?.lectures, progress]);
  const requestUndo = useCallback((token: string) => api<BankNext>("/api/bank/batch/undo", {
    method: "POST", body: JSON.stringify({ lectures: queue?.lectures, reviewToken: token }),
  }), [queue?.lectures]);
  const restore = useCallback((got: BankNext) => { progress(got); setDone(false); setPaused(false); }, [progress]);
  const { undo, undoBusy } = useBankUndo("/api/bank/batch", queue?.undoToken, restore, setError, !done && !paused, requestUndo);

  useEffect(() => {
    const previousTitle = document.title;
    document.title = "학습 현황 · Study_EZ";
    let live = true;
    function load() {
      const current = ++requestVersion.current;
      api<{ keys: string[] }>("/api/me/study-hidden")
        .then(hidden => { if (live && current === requestVersion.current) { setHiddenKeys(hidden.keys); setError(""); } })
        .catch((cause: Error) => { if (live && current === requestVersion.current) setError(cause.message); });
    }
    const refresh = () => load();
    load();
    window.addEventListener("focus", refresh);
    return () => { live = false; window.removeEventListener("focus", refresh); document.title = previousTitle; };
  }, [queue !== null, refreshKey]);
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

  async function setVisibility(keys: string[], hidden: boolean, count: number) {
    if (managing) return;
    ++requestVersion.current;
    setManaging(true); setManageMessage(""); setError("");
    try {
      const result = await api<{ keys: string[] }>("/api/me/study-hidden", {
        method: "PATCH", body: JSON.stringify({ keys, hidden }),
      });
      ++requestVersion.current;
      setHiddenKeys(result.keys);
      setManageMessage(`${count}강의를 ${hidden ? "숨겼습니다. ‘숨긴 강의’에서 복원할 수 있습니다." : "복원했습니다."}`);
    } catch (cause) { setError((cause as Error).message); }
    finally { setManaging(false); }
  }

  if (queue) return <>
    <div className="batch-progress" role="status">
      <span>강의 모아 풀기</span>
      <strong>{queue.lectures.length}강의 섞어 풀기{!done && current ? ` · ${current.title}` : ""}</strong>
      <button className="is-quiet" disabled={saving} onClick={() => { setQueue(null); setDone(false); setPaused(false); setError(""); }}>강의 다시 선택</button>
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

  return <>
    {error ? <p className="notice is-error" role="alert">{error}</p> : null}
    {loadError ? <p className="notice is-error" role="alert">{loadError}{" "}
      <button onClick={() => setRefreshKey(old => old + 1)}>다시 시도</button></p> : null}
    {manageMessage ? <p className="notice" role="status">{manageMessage}</p> : null}
    {deleting ? <DeleteQuizDialog lectures={deleting} onClose={() => setDeleting(null)} onDeleted={keys => {
      setEvents(old => old?.map(event => ({ ...event, lectures: event.lectures.map(l => keys.includes(`${l.subject}/${l.runId}`)
        ? { ...l, marks: { ...l.marks, quiz: false }, bankTimeline: null, cardProgress: null, mastery: null } : l) })) ?? null);
      setManageMessage(`${keys.length}강의의 퀴즈를 삭제했습니다.`);
      setRefreshKey(old => old + 1);
    }} /> : null}
    {!events ? !loadError && <p className="notice" role="status">강의 목록을 불러오는 중…</p>
      : <StudyOverview events={events} hiddenKeys={hiddenKeys} managing={managing || auditing || deleting !== null}
        onScope={onScope}
        onVisibility={(keys, hidden, count) => void setVisibility(keys, hidden, count)} onDeleteQuiz={me?.isAdmin ? setDeleting : undefined} onStart={chosen => {
        setPaused(false); setDone(false);
        setQueue({ lectures: chosen.map(({ subject, runId, title, date }) => ({ subject, runId, title, date })) });
      }} adminActions={me?.isAdmin ? chosen => <>
        <button className="is-quiet" disabled={!chosen.length || auditing} onClick={() => void (async () => {
          setAuditing(true); setAuditMessage("");
          const failures: string[] = [];
          let requested = 0;
          for (const lecture of chosen) {
            try {
              await api(`/api/admin/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}/bank/audit`, { method: "POST" });
              requested++;
            } catch (cause) { failures.push(`${lecture.title}: ${(cause as Error).message}`); }
          }
          setAuditMessage(`${requested}강의 검증·보강 요청 완료${failures.length ? ` · 요청 실패 ${failures.join(" / ")}` : " · 러너가 처리합니다. 기존 카드로 계속 공부할 수 있습니다."}`);
          setAuditing(false);
        })()}>{auditing ? "요청 중…" : "선택 강의 누락 검증·객관식 보강"}</button>
        {auditMessage ? <p role="status" className="bank-note">{auditMessage}</p> : null}
      </> : undefined} />}
  </>;
}
