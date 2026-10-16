import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import { QuestionEditor } from "../admin/BankCardReview";
import { bumpPreviewVersion } from "../bridge/previewBridge";
import type { BankFullQuestion, BankReviewBoard } from "../types/bank";

export function CommonQuestionDialog({ subject, runId, questionId, onClose, onSaved }: {
  subject: string; runId: string; questionId: string; onClose: () => void; onSaved: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [board, setBoard] = useState<BankReviewBoard | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { dialog.current?.showModal(); }, []);
  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ subject, runId, questionId });
    api<BankReviewBoard>(`/api/admin/bank-review?${query}`, { signal: controller.signal }).then(result => {
      if (controller.signal.aborted) return;
      if (!result.banks.some(group => group.cards.some(card => card.question.question_id === questionId))) {
        setError("이 문항이 없습니다. 다시 생성되었거나 제외되었을 수 있습니다.");
      } else setBoard(result);
    }).catch(cause => { if (!controller.signal.aborted) setError((cause as Error).message); });
    return () => controller.abort();
  }, [subject, runId, questionId]);
  const group = board?.banks[0];
  const card = group?.cards.find(card => card.question.question_id === questionId);
  async function save(question: BankFullQuestion) {
    if (!group || !card || busy) return;
    setBusy(true); setError("");
    try {
      await api(`/api/admin/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/bank/cards/${encodeURIComponent(questionId)}`, {
        method: "PUT", body: JSON.stringify({ action: "edit", question, buildId: group.buildId, expectedQuestion: card.question }),
      });
      bumpPreviewVersion();
      onSaved();
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  return createPortal(<dialog ref={dialog} className="bank-feedback-dialog bank-common-dialog" aria-labelledby="bank-common-title"
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <header><h2 id="bank-common-title">공용 문제 수정</h2>
      <button type="button" className="is-quiet" disabled={busy} aria-label="공용 수정창 닫기" onClick={onClose}>×</button></header>
    <p className="bank-feedback-id">{subject} · {runId} · {questionId}</p>
    <p>저장하면 모든 사용자의 문제에 반영됩니다.</p>
    {!board && !error ? <p role="status">문항을 불러오는 중…</p> : null}
    {card && group ? <QuestionEditor question={card.question} group={group} busy={busy} onSave={save} onCancel={onClose} /> : null}
    {error ? <p className="notice is-error" role="alert">{error}</p> : null}
    {!card ? <button type="button" onClick={onClose}>닫기</button> : null}
  </dialog>, document.body);
}
