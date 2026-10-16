import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { takeTimetable } from "../firstScreen";
import type { TimetableEvent } from "../types/lectures";

/** 처음에는 목록만 읽는다. 학습률은 켜 둔 경우에만 현재 격자 범위로 읽는다. */
export function useCalendarTimetable(start: string, end: string, showLearning: boolean) {
  const [events, setEvents] = useState<TimetableEvent[] | null>(null);
  const [error, setError] = useState("");
  const [learningError, setLearningError] = useState("");
  const [learningLoading, setLearningLoading] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [baseVersion, setBaseVersion] = useState(0);
  const lastLoaded = useRef(0);
  const reload = useCallback(() => setRefreshVersion(old => old + 1), []);

  useEffect(() => {
    let live = true;
    takeTimetable().then(data => {
      if (!live) return;
      setEvents(data.events); setError("");
      lastLoaded.current = Date.now();
      setBaseVersion(old => old + 1);
    }).catch((cause: Error) => { if (live) setError(cause.message); });
    return () => { live = false; };
  }, [refreshVersion]);

  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === "visible" && Date.now() - lastLoaded.current >= 60_000) reload();
    };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [reload]);

  useEffect(() => {
    setLearningError("");
    if (!showLearning || !baseVersion) { setLearningLoading(false); return; }
    const controller = new AbortController();
    setLearningLoading(true);
    const query = new URLSearchParams({ start, end, include_cards: "false" });
    api<{ events: TimetableEvent[] }>(`/api/timetable?${query}`, { signal: controller.signal })
      .then(data => {
        if (controller.signal.aborted) return;
        const enriched = new Map(data.events.map(e => [e.id, e]));
        setEvents(old => old?.map(e => enriched.get(e.id) ?? e) ?? null);
      }).catch((cause: Error) => { if (!controller.signal.aborted) setLearningError(cause.message); })
      .finally(() => { if (!controller.signal.aborted) setLearningLoading(false); });
    return () => controller.abort();
  }, [start, end, showLearning, baseVersion]);

  return { events, error, learningError, learningLoading, reload };
}
