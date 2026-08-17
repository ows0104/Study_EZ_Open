import { useEffect, useState } from "react";
import { api } from "../api";
import { DEFAULT_PREVIEW_PROMPT } from "./previewPrompt";

/**
 * 내 예습 프롬프트.
 *
 * 서버에 빈 문자열로 있으면 "아직 안 고쳤다"는 뜻이고 기본값을 쓴다. 저장할 때
 * 기본값과 같으면 다시 빈 문자열로 되돌린다 — 그래야 기본 문구가 나중에 바뀔 때
 * 안 고친 사람들이 같이 따라온다.
 *
 * 패널은 칸을 누를 때마다 새로 뜨므로 값을 모듈에 한 번만 받아 둔다. 매번 다시
 * 부르면 칸을 옮겨 다닐 때마다 요청이 나간다.
 */
let cached: string | null = null;
const waiting = new Set<(value: string) => void>();

export function usePreviewPrompt() {
  const [stored, setStored] = useState<string | null>(cached);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (cached !== null) return;
    let live = true;
    waiting.add(setStored);
    api<{ prompt: string }>("/api/me/preview-prompt")
      .then((payload) => {
        cached = payload.prompt;
        waiting.forEach((notify) => notify(payload.prompt));
        waiting.clear();
      })
      .catch(() => {
        // 못 받아도 예습은 되어야 한다. 기본값으로 간다.
        cached = "";
        if (live) setStored("");
      });
    return () => {
      live = false;
      waiting.delete(setStored);
    };
  }, []);

  async function save(next: string) {
    const trimmed = next.trim();
    // 기본값과 같으면 저장하지 않고 비운다. "안 고친 사람"으로 남는다는 뜻이다.
    const value = trimmed === DEFAULT_PREVIEW_PROMPT.trim() ? "" : trimmed;
    setSaving(true);
    try {
      await api("/api/me/preview-prompt", { method: "PUT", body: JSON.stringify({ prompt: value }) });
      cached = value;
      setStored(value);
    } finally {
      setSaving(false);
    }
  }

  return {
    /** 서버에서 아직 안 왔으면 null. 온 뒤에는 빈 문자열이거나 고친 문구다. */
    loaded: stored !== null,
    template: stored || DEFAULT_PREVIEW_PROMPT,
    isCustom: Boolean(stored),
    saving,
    save,
    reset: () => save(""),
  };
}
