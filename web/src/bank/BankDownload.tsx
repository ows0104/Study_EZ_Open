import { useState } from "react";
import { downloadSignedFile } from "../api";

/** Download the whole current bank; Anki keeps its own study schedule. */
export function BankDownload({ lecture, count }: {
  lecture: { subject: string; runId: string };
  count: number;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function download() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await downloadSignedFile(
        `/api/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}/bank/anki`,
        `${lecture.runId} QuizBank.apkg`,
      );
      window.dispatchEvent(new Event("studyez:bank-downloaded"));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button className="resource is-download" disabled={busy} aria-busy={busy} onClick={() => void download()}>
        <strong>{busy ? "Anki 덱 준비 중…" : "Main-Quiz Anki 덱 받기"}</strong>
        <small>Quiz Bank 전체 {count}문항 · 정답과 근거 슬라이드 포함</small>
      </button>
      {error ? <p className="notice is-error">{error}</p> : null}
    </>
  );
}
