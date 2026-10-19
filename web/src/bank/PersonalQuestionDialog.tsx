import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import type { BankAnswer, BankQuestion } from "../types/bank";
import { FEEDBACK } from "./feedback";

type Snapshot = {
  original: { question: string; answer: string; explanation?: string };
  draft: { question: string; answer: string; explanation?: string };
  edited: boolean;
  revision: string;
  comment: string;
  personalAdded?: boolean;
};
export type PersonalQuestionResult = { question: BankQuestion; answer: BankAnswer; reported: boolean; highlighted?: boolean };

export function PersonalQuestionDialog({ base, questionId, answerVisible, onClose, onSaved }: {
  base: string; questionId: string; answerVisible: boolean; onClose: () => void;
  onSaved: (result: PersonalQuestionResult, reset: boolean) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [explanation, setExplanation] = useState("");
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
      setExplanation(next.draft.explanation ?? "");
      setComment(next.comment);
    }).catch(cause => { if (live) setError((cause as Error).message); });
    return () => { live = false; };
  }, [path]);
  useEffect(() => { if (snapshot) dialog.current?.querySelector("textarea")?.focus(); }, [snapshot]);
  const changed = snapshot && (question.trim() !== snapshot.original.question || answer.trim() !== snapshot.original.answer
    || (snapshot.personalAdded && explanation.trim() !== (snapshot.original.explanation ?? "")));
  const noteChanged = snapshot && comment.trim() !== snapshot.comment;
  async function save(reset = false) {
    if (busy || !snapshot) return;
    setBusy(true); setError("");
    try {
      const result = await api<PersonalQuestionResult>(path, { method: "PUT", body: JSON.stringify({
        action: reset ? "reset" : "save", revision: snapshot.revision,
        question: reset ? snapshot.original.question : question,
        answer: reset ? snapshot.original.answer : answer, report: !reset && report, category, comment,
        ...(snapshot.personalAdded ? { explanation } : {}),
      }) });
      onSaved(result, reset);
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  return createPortal(<dialog ref={dialog} className="bank-feedback-dialog" aria-labelledby="bank-feedback-title"
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <form onSubmit={event => { event.preventDefault(); void save(); }}>
      <header><h2 id="bank-feedback-title">{snapshot?.personalAdded ? "내가 추가한 문제 수정" : "문제 수정·제보"}</h2>
        <button type="button" className="is-quiet" aria-label="수정창 닫기" disabled={busy} onClick={onClose}>×</button></header>
      <p className="bank-feedback-id">문항 {questionId}</p>
      <p className="bank-personal-hint">수정 내용은 내 계정에만 적용됩니다. 다른 사람의 문제는 바뀌지 않습니다.</p>
      {snapshot && !snapshot.personalAdded ? <p className="bank-personal-hint">수정 내용과 피드백은 관리자에게 전달됩니다. 제보 강조를 선택하면 더 눈에 띄게 표시됩니다.</p> : null}
      {!snapshot && !error ? <p role="status">문항을 불러오는 중…</p> : null}
      {snapshot ? <>
        <label>발문<textarea disabled={busy} required rows={3} maxLength={12000} value={question} onChange={e => setQuestion(e.target.value)} /></label>
        <details className="bank-personal-answer" open={answerVisible || undefined}>
          <summary>정답 확인·수정</summary>
          <label>정답<textarea disabled={busy} required rows={4} maxLength={12000} value={answer} onChange={e => setAnswer(e.target.value)} /></label>
          <small>정답을 수정한 문항은 내 수정본을 기준으로 직접 평가합니다.</small>
        </details>
        {snapshot.personalAdded ? <label>설명 (선택)<textarea disabled={busy} rows={3} maxLength={12000}
          value={explanation} onChange={event => setExplanation(event.target.value)} /></label> : null}
        {!snapshot.personalAdded ? <><details className="bank-personal-original"><summary>공용 원문 보기</summary>
          <p>{snapshot.original.question}</p><p>{snapshot.original.answer}</p></details>
        <label>피드백 (선택)<textarea disabled={busy} rows={3} maxLength={2000} value={comment}
          placeholder="수정 이유나 문제점을 적어 주세요." onChange={e => setComment(e.target.value)} /></label>
        <label className="bank-personal-report"><input type="checkbox" disabled={busy} checked={report} onChange={e => setReport(e.target.checked)} />제보 강조</label>
        {report ? <label>제보 유형<select disabled={busy} value={category} onChange={e => setCategory(e.target.value)}>
          {FEEDBACK.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select><small>관리자 피드백함에 강조 표시하고 우선 노출합니다.</small></label> : null}</> : null}
      </> : null}
      {error ? <p className="notice is-error" role="alert">{error}</p> : null}
      <footer>
        {snapshot?.edited && !snapshot.personalAdded ? <button type="button" disabled={busy} onClick={() => void save(true)}>원본으로 되돌리기</button> : null}
        <button type="button" className="is-quiet" disabled={busy} onClick={onClose}>취소</button>
        {snapshot ? <button type="submit" disabled={busy || (!changed && !noteChanged && !report)}>
          {busy ? "저장하는 중…" : report ? changed || noteChanged ? "내 수정본 저장·제보" : "제보 보내기" : "내 수정본 저장"}
        </button> : null}
      </footer>
    </form>
  </dialog>, document.body);
}
