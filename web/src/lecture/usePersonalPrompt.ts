import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";

type PromptKind = "preview" | "review";
type PromptCache = { stored?: string; pending?: Promise<string>; listeners: Set<(value: string) => void> };
const caches = new Map<string, PromptCache>();

export function usePersonalPrompt(kind: PromptKind, defaultPrompt: string) {
  const account = useAuth().session?.user.id ?? "local";
  const key = `${account}:${kind}`;
  if (!caches.has(key)) caches.set(key, { listeners: new Set() });
  const cache = caches.get(key)!;
  const [stored, setStored] = useState<string | null>(cache.stored ?? null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    cache.listeners.add(setStored);
    setStored(cache.stored ?? null);
    setError("");
    if (cache.stored === undefined) {
      const request = cache.pending ??= api<{ prompt: string }>(`/api/me/${kind}-prompt`)
        .then(({ prompt }) => {
          cache.stored = prompt;
          cache.listeners.forEach((notify) => notify(prompt));
          return prompt;
        }).finally(() => { delete cache.pending; });
      request.catch(() => {
        if (live) setError("저장된 프롬프트를 불러오지 못했습니다. 강의 패널을 다시 열어 주세요.");
      });
    }
    return () => { live = false; cache.listeners.delete(setStored); };
  }, [cache, kind]);

  async function save(next: string) {
    const trimmed = next.trim();
    const value = trimmed === defaultPrompt.trim() ? "" : trimmed;
    setSaving(true);
    try {
      await api(`/api/me/${kind}-prompt`, { method: "PUT", body: JSON.stringify({ prompt: value }) });
      cache.stored = value;
      cache.listeners.forEach((notify) => notify(value));
      setError("");
    } finally { setSaving(false); }
  }

  return {
    loaded: stored !== null, template: stored || defaultPrompt, isCustom: Boolean(stored),
    saving, error, save, reset: () => save(""),
  };
}
