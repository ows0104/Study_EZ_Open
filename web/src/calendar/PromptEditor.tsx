import { useState } from "react";
import { PROMPT_TOKENS, renderPreviewPrompt } from "../lecture/previewPrompt";
import type { usePersonalPrompt } from "../lecture/usePersonalPrompt";
import { previewProviderLabels, previewProviders, type LectureDetail, type PreviewProvider } from "../types/lectures";

/** 계정에 저장하는 개인 예습·복습 프롬프트. 현재 강의로 자리표시자를 미리 확인한다. */
export function PromptEditor({
  store,
  detail,
  provider,
  onProvider,
  kind = "preview",
  render = renderPreviewPrompt,
  tokens = PROMPT_TOKENS,
  shared = false,
}: {
  store: ReturnType<typeof usePersonalPrompt>;
  detail: LectureDetail;
  provider: PreviewProvider;
  onProvider: (next: PreviewProvider) => void;
  kind?: "preview" | "review";
  render?: (template: string, detail: LectureDetail) => string;
  tokens?: ReadonlyArray<{ token: string; label: string }>;
  shared?: boolean;
}) {
  const purpose = kind === "review" ? "복습" : "예습";
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const text = draft ?? store.template;
  const dirty = draft !== null && draft.trim() !== store.template.trim();

  async function save() {
    setError("");
    setSaved(false);
    try {
      await store.save(text);
      setDraft(null);
      setSaved(true);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  async function reset() {
    setError("");
    setSaved(false);
    try {
      await store.reset();
      setDraft(null);
      setSaved(true);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  return (
    <div className="prompt-editor">
      <label className="prompt-editor-model">
        <span>어느 AI로 물을까</span>
        <select
          aria-label={`${purpose}에 쓸 AI`}
          value={provider}
          onChange={(event) => onProvider(event.target.value as PreviewProvider)}
        >
          {previewProviders.map((item) => <option value={item} key={item}>{previewProviderLabels[item]}</option>)}
        </select>
      </label>

      <h4 className="prompt-editor-label">{shared ? "기본 링크 — 모든 강의에 공통으로 적용" : "개인 링크 — 내가 고쳐 쓰는 것"}</h4>
      <textarea
        className="prompt-editor-text"
        value={text}
        disabled={!store.loaded || store.saving}
        spellCheck={false}
        onChange={(event) => { setDraft(event.target.value); setSaved(false); }}
        maxLength={shared ? 20000 : undefined}
        aria-label={`${shared ? "기본 " : ""}${purpose} 프롬프트`}
      />
      <p className="prompt-editor-tokens">
        {tokens.map(({ token, label }) => (
          <button
            key={token}
            type="button"
            disabled={!store.loaded || store.saving}
            title={`${label} 넣기`}
            onClick={() => setDraft(`${text}${text.endsWith("\n") ? "" : " "}${token}`)}
          >
            {token}
          </button>
        ))}
        <span>누르면 끝에 붙습니다</span>
      </p>
      <div className="prompt-editor-actions">
        <button className="is-primary" onClick={save} disabled={!store.loaded || !dirty || store.saving}>
          {store.saving ? "저장 중…" : "저장"}
        </button>
        <button className="is-quiet" onClick={reset} disabled={!store.loaded || !store.isCustom || store.saving}>
          기본값으로
        </button>
        {draft !== null ? (
          <button className="is-quiet" onClick={() => setDraft(null)} disabled={store.saving}>
            되돌리기
          </button>
        ) : null}
      </div>
      <p className="prompt-editor-tokens">{shared ? "저장한 문구는 모든 강의의 기본 예습 링크를 새로 만들 때 사용합니다. 기존 대화는 그대로 유지됩니다." : `저장한 문구는 새 ${purpose} 대화를 만들 때 사용합니다.`}</p>
      {saved && !dirty ? <p role="status">저장했습니다.</p> : null}
      {store.error ? <p className="prompt-editor-error">{store.error}</p> : null}
      {error ? <p className="prompt-editor-error">{error}</p> : null}
      <details className="prompt-editor-preview">
        <summary>이 강의로 채워 보기</summary>
        <pre>{render(text, detail)}</pre>
      </details>
    </div>
  );
}
