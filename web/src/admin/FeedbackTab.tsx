import { useCallback, useEffect, useState } from "react";
import { api, apiBytes } from "../api";
import { ADMIN_REFRESH_MS, refreshDue } from "./jobUpdates";
import "../styles/feedback.css";

type Feedback = {
  id: number; email: string; message: string; page: string;
  status: "open" | "resolved"; createdAt: string; screenshots: { name: string }[];
};
function Screenshot({ id, index, name }: { id: number; index: number; name: string }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true; let objectUrl = "";
    apiBytes(`/api/admin/feedback/${id}/screenshots/${index}`).then((data) => {
      if (!active) return;
      const type = data[0] === 0x89 ? "image/png" : data[0] === 0xff ? "image/jpeg" : "image/webp";
      objectUrl = URL.createObjectURL(new Blob([new Uint8Array(data)], { type })); setUrl(objectUrl);
    }).catch((cause: Error) => { if (active) setError(cause.message); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [id, index]);
  return <figure>{error ? <p role="alert">{error}</p> : url ?
    <a href={url} target="_blank" rel="noreferrer"><img src={url} alt={name} /></a> : <p>캡처 불러오는 중…</p>}
    <figcaption>{name}</figcaption></figure>;
}
function FeedbackCard({ row, busy, onChange }: { row: Feedback; busy: number | null; onChange: () => void }) {
  const [expanded, setExpanded] = useState(false);
  return <article className="feedback-card">
    <header><strong>{row.email}</strong><span>{row.status === "open" ? "미처리" : "처리 완료"}</span></header>
    <small>{new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(row.createdAt) ? row.createdAt : `${row.createdAt}Z`).toLocaleString("ko-KR")}</small>
    <p className="feedback-message">{row.message}</p><p className="feedback-context">화면: {row.page}</p>
    {row.screenshots.length ? <details onToggle={(event) => setExpanded(event.currentTarget.open)}>
      <summary>화면 캡처 {row.screenshots.length}장</summary><div className="feedback-shots">
        {expanded ? row.screenshots.map((shot, index) =>
          <Screenshot key={index} id={row.id} index={index} name={shot.name} />) : null}
      </div></details> : null}
    <button disabled={busy !== null} onClick={onChange}>
      {busy === row.id ? "저장 중…" : row.status === "open" ? "처리 완료" : "다시 열기"}</button>
  </article>;
}
export function FeedbackTab() {
  const [rows, setRows] = useState<Feedback[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [lastReadAt, setLastReadAt] = useState(0);
  const load = useCallback(() => {
    api<Feedback[]>("/api/admin/feedback").then((data) => { setRows(data); setError(""); })
      .catch((cause: Error) => setError(cause.message))
      .finally(() => setLastReadAt(Date.now()));
  }, []);
  useEffect(load, [load]);
  useEffect(() => {
    const timer = window.setTimeout(() => { if (!document.hidden) load(); }, ADMIN_REFRESH_MS);
    const visible = () => { if (!document.hidden && refreshDue(lastReadAt)) load(); };
    document.addEventListener("visibilitychange", visible);
    return () => { window.clearTimeout(timer); document.removeEventListener("visibilitychange", visible); };
  }, [load, lastReadAt]);
  async function change(row: Feedback) {
    setBusy(row.id);
    try {
      const status = row.status === "open" ? "resolved" : "open";
      await api(`/api/admin/feedback/${row.id}`, { method: "PATCH", body: JSON.stringify({ status }) }); load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "저장하지 못했습니다."); }
    finally { setBusy(null); }
  }
  return <section className="feedback-board">
    <header><h2>피드백함</h2><button onClick={load}>새로고침</button></header>
    <p>최근 200건 · 미처리 {rows?.filter((row) => row.status === "open").length ?? 0}건 · 10분마다 갱신</p>
    {error ? <p className="notice is-error" role="alert">{error}</p> : null}
    {!rows ? <p>불러오는 중…</p> : !rows.length ? <p>아직 받은 피드백이 없습니다.</p> :
      rows.map((row) => <FeedbackCard key={row.id} row={row} busy={busy} onChange={() => void change(row)} />)}
  </section>;
}
