import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import type { BankAnswer, BankQuestion } from "../types/bank";
import { FEEDBACK } from "./feedback";

type Snapshot = {
  original: { question: string; answer: string };
  draft: { question: string; answer: string };
  edited: boolean;
  revision: string;
  comment: string;
};
export type PersonalQuestionResult = { question: BankQuestion; answer: BankAnswer; reported: boolean };

export function PersonalQuestionDialog({ base, questionId, answerVisible, onClose, onSaved }: {
  base: string; questionId: string; answerVisible: boolean; onClose: () => void;
  onSaved: (result: PersonalQuestionResult, reset: boolean) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [category, setCategory] = useState("content");
  const [comment, setComment] = useState("");
  const [report, setReport] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const path = `${base}/questions/${encodeURIComponent(questionId)}/personal`;
  useEffect(() => { dialog.current?.showModal(); }, []);
  useEffect(() => {
    let live = true;
    api<Snapshot>(path).then(next => {
      if (!live) return;
      setSnapshot(next); setQuestion(next.draft.question); setAnswer(next.draft.answer);
      setComment(next.comment);
    }).catch(cause => { if (live) setError((cause as Error).message); });
    return () => { live = false; };
  }, [path]);
  useEffect(() => { if (snapshot) dialog.current?.querySelector("textarea")?.focus(); }, [snapshot]);
  const changed = snapshot && (question.trim() !== snapshot.original.question || answer.trim() !== snapshot.original.answer);
  const noteChanged = snapshot && comment.trim() !== snapshot.comment;
  async function save(reset = false) {
    if (busy || !snapshot) return;
    setBusy(true); setError("");
    try {
      const result = await api<PersonalQuestionResult>(path, { method: "PUT", body: JSON.stringify({
        action: reset ? "reset" : "save", revision: snapshot.revision,
        question: reset ? snapshot.original.question : question,
        answer: reset ? snapshot.original.answer : answer, report: !reset && report, category, comment,
      }) });
      onSaved(result, reset);
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  return createPortal(<dialog ref={dialog} className="bank-feedback-dialog" aria-labelledby="bank-feedback-title"
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <form onSubmit={event => { event.preventDefault(); void save(); }}>
      <header><h2 id="bank-feedback-title">문제 수정·제보</h2>
        <button type="button" className="is-quiet" aria-label="수정창 닫기" disabled={busy} onClick={onClose}>×</button></header>
      <p className="bank-feedback-id">문항 {questionId}</p>
      <p className="bank-personal-hint">수정 내용은 내 계정에만 적용됩니다. 다른 사람의 문제는 바뀌지 않습니다.</p>
      {!snapshot && !error ? <p role="status">문항을 불러오는 중…</p> : null}
      {snapshot ? <>
        <label>발문<textarea disabled={busy} required rows={3} maxLength={12000} value={question} onChange={e => setQuestion(e.target.value)} /></label>
        <details className="bank-personal-answer" open={answerVisible || undefined}>
          <summary>정답 확인·수정</summary>
          <label>정답<textarea disabled={busy} required rows={4} maxLength={12000} value={answer} onChange={e => setAnswer(e.target.value)} /></label>
          <small>정답을 수정한 문항은 내 수정본을 기준으로 직접 평가합니다.</small>
        </details>
        <details className="bank-personal-original"><summary>공용 원문 보기</summary>
          <p>{snapshot.original.question}</p><p>{snapshot.original.answer}</p></details>
        <label>{report ? "피드백 (선택)" : "개인 메모 (선택)"}<textarea disabled={busy} rows={3} maxLength={2000} value={comment}
          placeholder="수정 이유나 문제점을 적어 주세요." onChange={e => setComment(e.target.value)} /></label>
        <label className="bank-personal-report"><input type="checkbox" disabled={busy} checked={report} onChange={e => setReport(e.target.checked)} />관리자에게도 제보</label>
        {report ? <label>제보 유형<select disabled={busy} value={category} onChange={e => setCategory(e.target.value)}>
          {FEEDBACK.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select><small>피드백과 수정 제안을 함께 보냅니다. 공용 문제에는 자동 반영되지 않습니다.</small></label> : null}
      </> : null}
      {error ? <p className="notice is-error" role="alert">{error}</p> : null}
      <footer>
        {snapshot?.edited ? <button type="button" disabled={busy} onClick={() => void save(true)}>원본으로 되돌리기</button> : null}
        <button type="button" className="is-quiet" disabled={busy} onClick={onClose}>취소</button>
        {snapshot ? <button type="submit" disabled={busy || (!changed && !noteChanged && !report)}>
          {busy ? "저장하는 중…" : report ? changed || noteChanged ? "내 수정본 저장·제보" : "제보 보내기" : "내 수정본 저장"}
        </button> : null}
      </footer>
    </form>
  </dialog>, document.body);
}
