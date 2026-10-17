import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import { invalidateTimetable } from "../firstScreen";
import type { BankRead, BankTier } from "../types/bank";
import { PersonalQuestionDialog } from "./PersonalQuestionDialog";
import { initialSettings, PersonalQuestionSettings, settingsPayload } from "./PersonalQuestionSettings";

export const TIER_LABELS: Record<BankTier, string> = {
  Essential: "★ Must-Know", Core: "Core", Important: "Important", Optional: "Optional",
};

export function AddQuestionDialog({ base, sourceQuestionId, onClose, onSaved }: {
  base: string; sourceQuestionId?: string; onClose: () => void; onSaved: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [clientId] = useState(() => crypto.randomUUID());
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [explanation, setExplanation] = useState("");
  const [tier, setTier] = useState<BankTier>("Core");
  const [settings, setSettings] = useState(initialSettings);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  useEffect(() => { dialog.current?.showModal(); }, []);
  async function save() {
    if (pending.current || !question.trim() || !answer.trim()) return;
    pending.current = true; setBusy(true); setError("");
    try {
      await api(`${base}/personal-questions`, { method: "POST", body: JSON.stringify({
        clientId, question, answer, explanation, tier, sourceQuestionId, ...settingsPayload(settings),
      }) });
      invalidateTimetable(); onSaved();
    } catch (cause) { setError((cause as Error).message); }
    finally { pending.current = false; setBusy(false); }
  }
  return createPortal(<dialog ref={dialog} className="bank-feedback-dialog" aria-labelledby="add-question-title"
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <form onSubmit={event => { event.preventDefault(); void save(); }}>
      <header><h2 id="add-question-title">내 문제 추가</h2>
        <button type="button" className="is-quiet" aria-label="추가창 닫기" disabled={busy} onClick={onClose}>×</button></header>
      <p className="bank-personal-hint">내 계정의 이 강의에만 추가됩니다. 문항 형식과 회상 방식을 선택하고, 풀이 후 직접 평가합니다.</p>
      {sourceQuestionId ? <p className="bank-personal-hint">현재 보고 있는 문제의 슬라이드가 참고 자료로 자동 연결됩니다.</p> : null}
      <PersonalQuestionSettings value={settings} onChange={setSettings} busy={busy} />
      <label>발문<textarea autoFocus required rows={3} maxLength={12000} value={question} disabled={busy}
        placeholder="무엇을 떠올릴지 질문으로 적어 주세요." onChange={event => setQuestion(event.target.value)} /></label>
      <label>정답<textarea required rows={4} maxLength={12000} value={answer} disabled={busy}
        onChange={event => setAnswer(event.target.value)} /></label>
      <label>설명 (선택)<textarea rows={3} maxLength={12000} value={explanation} disabled={busy}
        onChange={event => setExplanation(event.target.value)} /></label>
      <label>중요도<select value={tier} disabled={busy} onChange={event => setTier(event.target.value as BankTier)}>
        {Object.entries(TIER_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select><small>Must-Know: 교수님이 직접·간접적으로 알아야 한다고 강조하거나 시험 출제를 예고한 내용</small></label>
      {error ? <p className="notice is-error" role="alert">{error}</p> : null}
      <footer><button type="button" className="is-quiet" disabled={busy} onClick={onClose}>취소</button>
        <button type="submit" disabled={busy || !question.trim() || !answer.trim()}>{busy ? "추가하는 중…" : "내 학습에 추가"}</button></footer>
    </form>
  </dialog>, document.body);
}

export function PersonalQuestions({ base, info, onChanged }: { base: string; info: BankRead; onChanged: () => void }) {
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function remove(questionId: string) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      await api(`${base}/personal-questions/${encodeURIComponent(questionId)}`, { method: "DELETE" });
      invalidateTimetable(); setDeleting(null); onChanged();
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  const questions = info.personalQuestions ?? [];
  return <section className="bank-personal-questions" aria-label="내가 추가한 문제">
    <button className="is-quiet" onClick={() => setAdding(true)}>＋ 문제 추가</button>
    {questions.length ? <details><summary>내가 추가한 문제 {questions.length}개</summary>
      <ul>{questions.map(q => <li key={q.questionId}>
        <span><small className={q.tier === "Essential" ? "is-essential" : ""}>{TIER_LABELS[q.tier]}</small> {q.question}</span>
        <button className="is-quiet" disabled={busy} onClick={() => setEditing(q.questionId)}>수정</button>
        {deleting === q.questionId ? <>
          <span>이 문제를 삭제할까요?</span>
          <button disabled={busy} onClick={() => void remove(q.questionId)}>삭제 확인</button>
          <button className="is-quiet" disabled={busy} onClick={() => setDeleting(null)}>취소</button>
        </> : <button className="is-quiet" disabled={busy} onClick={() => setDeleting(q.questionId)}>삭제</button>}
      </li>)}</ul>
    </details> : null}
    {error ? <p className="notice is-error" role="alert">{error}</p> : null}
    {adding ? <AddQuestionDialog base={base} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); onChanged(); }} /> : null}
    {editing ? <PersonalQuestionDialog base={base} questionId={editing} answerVisible onClose={() => setEditing(null)}
      onSaved={() => { invalidateTimetable(); setEditing(null); onChanged(); }} /> : null}
  </section>;
}
