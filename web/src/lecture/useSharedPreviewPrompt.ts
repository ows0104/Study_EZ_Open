import { useEffect, useState } from "react";
import { api } from "../api";
import { SHARED_PREVIEW_PROMPT } from "./previewPrompt";

const path = "/api/admin/preview-prompt";

export async function readSharedPreviewPrompt() {
  const { prompt } = await api<{ prompt: string }>(path);
  return prompt || SHARED_PREVIEW_PROMPT;
}

export function useSharedPreviewPrompt(enabled: boolean) {
  const [stored, setStored] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!enabled) return;
    let live = true;
    api<{ prompt: string }>(path).then(({ prompt }) => {
      if (live) { setStored(prompt); setError(""); }
    }).catch(() => {
      if (live) setError("기본 프롬프트를 불러오지 못했습니다. 강의 패널을 다시 열어 주세요.");
    });
    return () => { live = false; };
  }, [enabled]);

  async function save(next: string) {
    setSaving(true);
    try {
      const value = next.trim() === SHARED_PREVIEW_PROMPT.trim() ? "" : next.trim();
      const { prompt } = await api<{ prompt: string }>(path, {
        method: "PUT", body: JSON.stringify({ prompt: value }),
      });
      setStored(prompt);
      setError("");
    } finally { setSaving(false); }
  }

  return {
    loaded: stored !== null, template: stored || SHARED_PREVIEW_PROMPT,
    isCustom: Boolean(stored), saving, error, save, reset: () => save(""),
  };
}
