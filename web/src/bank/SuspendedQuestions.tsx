import { useState } from "react";
import { api } from "../api";
import { invalidateTimetable } from "../firstScreen";
import { Stem } from "../lecture/Stem";
import type { BankRead } from "../types/bank";

export function SuspendedQuestions({ base, info, onChanged }: { base: string; info: BankRead; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const questions = info.suspendedQuestions ?? [];
  if (!questions.length) return null;
  async function resume(questionId: string) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      await api(`${base}/questions/${encodeURIComponent(questionId)}/suspension`, {
        method: "PUT", body: JSON.stringify({ suspended: false, buildId: info.summary.buildId }),
      });
      invalidateTimetable();
      onChanged();
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  return <details className="bank-suspended">
    <summary>비활성 문제 {questions.length}개</summary>
    <p className="bank-note">내 학습에서 제외한 문제입니다. 다시 활성화하면 출제 대상에 포함됩니다.</p>
    <ul>{questions.map(q => <li key={q.questionId}>
      <span><Stem text={q.question} /></span>
      <button className="is-quiet" disabled={busy} onClick={() => void resume(q.questionId)}>다시 활성화</button>
    </li>)}</ul>
    {error ? <p role="alert" className="notice is-error">{error}</p> : null}
  </details>;
}
