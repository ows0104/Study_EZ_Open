import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import type { StudyLecture } from "./StudyOverview";

export function DeleteQuizDialog({ lectures, onDeleted, onClose }: {
  lectures: StudyLecture[]; onDeleted: (keys: string[]) => void; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [deleted, setDeleted] = useState<string[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { dialog.current?.showModal(); }, []);
  const remaining = lectures.filter(l => !deleted.includes(l.key));
  async function remove() {
    if (busy || !remaining.length) return;
    setBusy(true); setError("");
    const removed: string[] = [];
    const failures: string[] = [];
    for (const lecture of remaining) {
      try {
        await api(`/api/admin/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}/bank?version=${encodeURIComponent(lecture.bankTimeline!.deleteVersion!)}`, { method: "DELETE" });
        removed.push(lecture.key);
      } catch (cause) { failures.push(`${lecture.title}: ${(cause as Error).message}`); }
    }
    setDeleted(old => [...old, ...removed]);
    if (removed.length) onDeleted(removed);
    setBusy(false);
    if (failures.length) setError(failures.join("\n"));
    else onClose();
  }
  return createPortal(<dialog ref={dialog} className="overview-delete-dialog" aria-labelledby="delete-quiz-title"
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <h2 id="delete-quiz-title">강의 퀴즈 전체 삭제</h2>
    <p>아래 {remaining.length}강의의 Main Quiz 전체가 삭제되어 <b>모든 사용자가 풀 수 없게 됩니다.</b></p>
    <ul>{lectures.map(l => <li key={l.key}>{l.title}<small>{l.date} · {l.subject}{deleted.includes(l.key) ? " · 삭제 완료" : ""}</small></li>)}</ul>
    <p>삭제 전 퀴즈 원본은 서버에 보관합니다. 강의록·예습퀴즈·개인 학습 기록은 유지됩니다.</p>
    {deleted.length ? <p role="status">{deleted.length}강의 삭제 완료</p> : null}
    {error ? <p role="alert" className="notice is-error">{error}</p> : null}
    <div className="overview-dialog-actions">
      <button className="is-quiet" disabled={busy} autoFocus onClick={onClose}>{deleted.length ? "닫기" : "취소"}</button>
      <button className="overview-delete" disabled={busy || !remaining.length} onClick={() => void remove()}>
        {busy ? "삭제 중…" : `${remaining.length}강의 퀴즈 삭제`}</button>
    </div>
  </dialog>, document.body);
}
