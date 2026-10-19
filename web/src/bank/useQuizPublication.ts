import { useEffect, useState } from "react";
import { api } from "../api";

export type QuizPublication = {
  subject: string; runId: string; shareUrl?: string; title?: string;
  responseSource?: "manual" | "link" | "file";
  link: { state: "complete" | "incomplete" | "wrong_lecture" | "unavailable" | "unsupported" | "unchecked" | "missing";
    sinceCutoff: boolean; completedAt: string | null; questionCount: number; checkedAt: string | null };
  upload: { sinceCutoff: boolean; current: boolean; builtAt: string | null };
  job: { state: string; stage: string } | null;
};

/** Refresh only the small production checklist, never the user's study aggregates. */
export function useQuizPublication(enabled: boolean) {
  const [values, setValues] = useState<QuizPublication[] | null>(null);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let controller: AbortController | null = null;
    let stopped = false;
    const refresh = async () => {
      if (document.hidden || controller) return;
      const active = new AbortController(); controller = active;
      try {
        const data = await api<{ lectures: QuizPublication[] }>("/api/timetable/quiz-publication", { signal: active.signal });
        if (!stopped) { setValues(data.lectures); setError(""); }
      } catch (cause) { if (!stopped && !active.signal.aborted) setError((cause as Error).message); }
      finally { if (controller === active) controller = null; }
    };
    void refresh();
    const tick = window.setInterval(() => void refresh(), 30_000);
    const focus = () => void refresh();
    window.addEventListener("focus", focus);
    document.addEventListener("visibilitychange", focus);
    return () => {
      stopped = true; controller?.abort(); window.clearInterval(tick);
      window.removeEventListener("focus", focus); document.removeEventListener("visibilitychange", focus);
    };
  }, [enabled, version]);
  return { values, error, refresh: () => setVersion(v => v + 1) };
}
