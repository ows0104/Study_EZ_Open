import { useState } from "react";
import { api } from "../api";
import { useMe } from "../useMe";
import type { LectureDetail } from "../types/lectures";
import { absoluteUrl, extensionCompatible, extensionInputMinimum, requestPreview } from "../bridge/previewBridge";
import { ExtensionSetup } from "../bridge/ExtensionSetup";
import { loadLatestBankPrompt } from "./prompt";

/** A human click prepares the latest prompt and attachments; sending stays manual. */
export function QuizCreateButton({ runId, title }: { runId: string; title: string }) {
  const isAdmin = Boolean(useMe()?.isAdmin);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [setup, setSetup] = useState(false);
  if (!isAdmin) return null;
  async function create() {
    if (busy) return;
    setError(""); setMessage(""); setSetup(false);
    if (!extensionCompatible(extensionInputMinimum("bank", false))) {
      setSetup(true); setError("브리지를 설치·업데이트하고 페이지를 새로고침하세요."); return;
    }
    setBusy(true);
    try {
      const path = `${encodeURIComponent("약리학")}/${encodeURIComponent(runId)}`;
      const detail = await api<LectureDetail>(`/api/lectures/${path}`);
      const sources = detail.bankSources ?? [];
      if (!sources.some(source => source.kind === "notes_current")) throw new Error("올해 강의 필기가 올라오면 만들 수 있습니다.");
      const latest = await loadLatestBankPrompt(detail, sources);
      const files = [];
      for (const source of sources) {
        const { url } = await api<{ url: string }>(`/api/lectures/${path}/files/${source.assetId}`);
        files.push({ id: source.assetId, filename: source.filename, downloadUrl: absoluteUrl(url), contentType: source.contentType });
      }
      await requestPreview({ requestId: `${runId}-bank-${performance.now()}`, lectureId: `약리학/${runId}`,
        provider: "chatgpt", mode: "bank", prompt: latest.prompt, promptVersion: latest.version, files, autoSend: false });
      setMessage(`프롬프트 ${latest.version} 준비 완료 · 열린 ChatGPT 대화에서 직접 전송하세요.`);
    } catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="quiz-create">
    <button className="is-quiet" disabled={busy} aria-label={`${title} 퀴즈 만들기`} onClick={() => void create()}>{busy ? "준비 중…" : "만들기"}</button>
    {message ? <small role="status">{message}</small> : null}
    {error ? <small role="alert">{error}</small> : null}
    {setup ? <ExtensionSetup minimum={extensionInputMinimum("bank", false)} /> : null}
  </div>;
}
