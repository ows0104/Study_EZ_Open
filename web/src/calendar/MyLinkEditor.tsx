import { useState } from "react";
import { api } from "../api";
import { bumpPreviewVersion } from "../bridge/previewBridge";
import { previewProviderLabels, previewProviders, type LectureRef, type PreviewProvider } from "../types/lectures";

/**
 * 개인 대화 ▾ 「링크 수정」(2026-11-13 사용자 지시: 자동 연결이 안 될 때 손으로 넣는다).
 *
 * 확장이 대화 주소를 못 돌려주면 대화는 AI 쪽에 있는데 칸은 비어 있다. 그 주소를
 * 붙여넣는 자리다. 저장은 확장이 쓰는 것과 같은 `PUT my-preview` / `my-review` 이고
 * 주소 꼴 검사도 서버의 그 자리에 있다. 비우고 저장하면 지운다.
 */
export function MyLinkEditor({
  lecture,
  kind,
  current,
  onDone,
}: {
  lecture: Pick<LectureRef, "subject" | "runId">;
  kind: "preview" | "review";
  current: { provider: PreviewProvider; conversationUrl: string } | null | undefined;
  onDone: () => void;
}) {
  const [provider, setProvider] = useState<PreviewProvider>(current?.provider ?? "chatgpt");
  const [url, setUrl] = useState(current?.conversationUrl ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const path = `${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;

  async function save() {
    setSaving(true);
    setError("");
    try {
      await api(`/api/lectures/${path}/${kind === "review" ? "my-review" : "my-preview"}`, {
        method: "PUT",
        body: JSON.stringify({ provider, conversationUrl: url.trim() }),
      });
      // 패널이 들고 있는 강의 상세를 다시 받게 한다(확장이 저장할 때와 같은 신호).
      bumpPreviewVersion();
      onDone();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="link-editor" onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <label className="link-editor-model">
        <span>AI</span>
        <select aria-label="개인 대화의 AI" value={provider}
          onChange={(event) => setProvider(event.target.value as PreviewProvider)}>
          {previewProviders.map((item) => (
            <option value={item} key={item}>{previewProviderLabels[item]}</option>
          ))}
        </select>
      </label>
      <label className="link-editor-field">
        <span>개인 대화 링크</span>
        <input value={url} placeholder="https://" spellCheck={false} autoFocus
          onChange={(event) => setUrl(event.target.value)} />
      </label>
      <div className="link-editor-actions">
        <button type="submit" className="is-primary" disabled={saving}>{saving ? "저장 중…" : "저장"}</button>
        <button type="button" onClick={onDone} disabled={saving}>취소</button>
      </div>
      {error ? <p className="prompt-editor-error">{error}</p> : null}
    </form>
  );
}
