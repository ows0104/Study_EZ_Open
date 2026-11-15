import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";

/** Main-Quiz 내 문제(2026-11-15, docs/changes/2026-11-15-root-personal-questions).
 * new: 지금 문항 자리에 빈 새 문제 · copy: 지금 문항을 내게 보이는 그대로 채워 새 문제 · edit: 내 문제 고치기. */
export type MineMode = "new" | "copy" | "edit";
type Draft = { question: string; answer: string; explanation: string; mine: boolean; enabled: boolean };
const TITLE: Record<MineMode, string> = { new: "이 자리에 새 문제", copy: "복사해서 고치기", edit: "내 문제 고치기" };

export function MineQuestionDialog({ base, mode, questionId, onClose, onSaved }: {
  /** `/api/root-learning/lectures/{subject}/{run_id}` */
  base: string; mode: MineMode; questionId: string; onClose: () => void; onSaved: (note: string) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [ready, setReady] = useState(mode === "new");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [explanation, setExplanation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { dialog.current?.showModal(); }, []);
  useEffect(() => {
    if (mode === "new") return;
    let live = true;
    api<Draft>(`${base}/questions/${encodeURIComponent(questionId)}/mine-draft`).then(draft => {
      if (!live) return;
      setQuestion(draft.question); setAnswer(draft.answer); setExplanation(draft.explanation); setReady(true);
    }).catch(cause => { if (live) setError((cause as Error).message); });
    return () => { live = false; };
  }, [base, mode, questionId]);
  useEffect(() => { if (ready) dialog.current?.querySelector("textarea")?.focus(); }, [ready]);
  async function save() {
    if (busy || !ready) return;
    setBusy(true); setError("");
    const body = { requestId: crypto.randomUUID(), question, answer, explanation };
    try {
      if (mode === "edit") {
        await api(`${base}/mine/${encodeURIComponent(questionId)}`, { method: "PUT", body: JSON.stringify({ ...body, action: "save" }) });
        onSaved("내 문제를 고쳤습니다.");
      } else {
        await api(`${base}/mine`, { method: "POST", body: JSON.stringify({ ...body, anchorQuestionId: questionId, copy: mode === "copy" }) });
        onSaved("내 문제를 만들었습니다. 이 문항 옆에서 복습 일정을 받고, 학습률에는 들어가지 않습니다.");
      }
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  return createPortal(<dialog ref={dialog} className="bank-feedback-dialog mq-mine-dialog" aria-labelledby="mq-mine-title"
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <form onSubmit={event => { event.preventDefault(); void save(); }}>
      <header><h2 id="mq-mine-title">{TITLE[mode]}</h2>
        <button type="button" className="is-quiet" aria-label="창 닫기" disabled={busy} onClick={onClose}>×</button></header>
      <p className="bank-personal-hint">내 계정에만 보이는 문제입니다. 원래 문항과 학습 기록은 바뀌지 않습니다.
        {mode !== "edit" ? " 이 문항 옆에서 복습 일정을 받고, 학습률·카드 수에는 들어가지 않습니다." : ""}</p>
      {!ready && !error ? <p role="status">문항을 불러오는 중…</p> : null}
      {ready ? <>
        <label>발문<textarea disabled={busy} required rows={4} maxLength={4000} value={question} onChange={e => setQuestion(e.target.value)} /></label>
        <label>정답<textarea disabled={busy} required rows={3} maxLength={4000} value={answer} onChange={e => setAnswer(e.target.value)} /></label>
        <label>해설 (선택)<textarea disabled={busy} rows={3} maxLength={4000} value={explanation} onChange={e => setExplanation(e.target.value)} /></label>
      </> : null}
      {error ? <p className="notice is-error" role="alert">{error}</p> : null}
      <footer>
        <button type="button" className="is-quiet" disabled={busy} onClick={onClose}>취소</button>
        {ready ? <button type="submit" disabled={busy || !question.trim() || !answer.trim()}>{busy ? "저장하는 중…" : "저장"}</button> : null}
      </footer>
    </form>
  </dialog>, document.body);
}

/** 답을 연 뒤 뒷면의 「내 메모」. 나만 본다. 입력하는 동안 풀이 단축키는 textarea라 동작하지 않는다. */
export type HintResult = { hint: string; clue: string; personalClue: boolean };

/** 내 힌트(2026-11-16): 답 보기 전에 펼치는 힌트 칸을 내 것으로 쓴다. 나만 보고, 비우면 원래 힌트(없으면 칸 없음)로. */
export function HintBox({ value, mine, path, onDone, onSaved, onError }: {
  value: string; mine: boolean; path: string; onDone: () => void;
  onSaved: (result: HintResult) => void; onError: (message: string) => void;
}) {
  const [text, setText] = useState(mine ? value : "");
  const [busy, setBusy] = useState(false);
  const area = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { area.current?.focus(); }, []);
  async function save(next: string) {
    if (busy) return;
    setBusy(true);
    try {
      onSaved(await api<HintResult>(path, { method: "PUT", body: JSON.stringify({ requestId: crypto.randomUUID(), text: next }) }));
      onDone();
    } catch (cause) { onError((cause as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="mq-memo mq-hint-edit">
    {value && !mine ? <p className="mq-memo-label">원래 힌트: {value}</p> : null}
    <label>내 힌트<textarea ref={area} rows={2} maxLength={1000} disabled={busy} value={text}
      placeholder={value && !mine ? "원래 힌트 대신 나에게만 보입니다." : "나만 보는 힌트. 답 보기 전에 「힌트 보기」로 펼칩니다."}
      onChange={e => setText(e.target.value)}
      onKeyDown={e => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void save(text); }
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onDone(); }
      }} /></label>
    <div className="mq-memo-actions">
      {mine ? <button type="button" className="is-quiet" disabled={busy} onClick={() => void save("")}>내 힌트 지우기</button> : null}
      <button type="button" className="is-quiet" disabled={busy} onClick={onDone}>취소</button>
      <button type="button" disabled={busy || !text.trim()} onClick={() => void save(text)}>{busy ? "저장하는 중…" : "저장"} <kbd>Ctrl+Enter</kbd></button>
    </div>
  </div>;
}

export function MemoBox({ value, path, disabled, onEditing, onSaved, onError }: {
  value: string; path: string; disabled: boolean; onEditing: (on: boolean) => void;
  onSaved: (memo: string) => void; onError: (message: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(value);
  const [busy, setBusy] = useState(false);
  const area = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (open) area.current?.focus(); }, [open]);
  function edit(on: boolean) { setOpen(on); setText(value); onEditing(on); }
  async function save() {
    if (busy) return;
    setBusy(true);
    try {
      const got = await api<{ memo: string }>(path, { method: "PUT", body: JSON.stringify({ requestId: crypto.randomUUID(), text }) });
      onSaved(got.memo); setOpen(false); onEditing(false);
    } catch (cause) { onError((cause as Error).message); }
    finally { setBusy(false); }
  }
  if (open) return <div className="mq-memo is-editing">
    <label>내 메모<textarea ref={area} rows={3} maxLength={2000} disabled={busy} value={text} placeholder="나만 보는 메모. 답을 연 뒤에 보입니다."
      onChange={e => setText(e.target.value)}
      onKeyDown={e => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void save(); }
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); edit(false); }
      }} /></label>
    <div className="mq-memo-actions">
      <button type="button" className="is-quiet" disabled={busy} onClick={() => edit(false)}>취소</button>
      <button type="button" disabled={busy} onClick={() => void save()}>{busy ? "저장하는 중…" : "저장"} <kbd>Ctrl+Enter</kbd></button>
    </div>
  </div>;
  return <div className="mq-memo">
    {value ? <><p className="mq-memo-label">내 메모</p><p className="mq-memo-text">{value}</p>
      <button type="button" className="is-quiet" disabled={disabled} onClick={() => edit(true)}>메모 고치기</button></>
      : <button type="button" className="is-quiet" disabled={disabled} onClick={() => edit(true)}>메모 쓰기</button>}
  </div>;
}
