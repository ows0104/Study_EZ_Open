import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { TimetableEvent } from "../types/lectures";

/**
 * 강의 목록의 시간표(학습 집계 없이). 운영 0.1–0.3 s.
 *
 * 2026-11-12까지는 받은 뒤 블럭 강의를 8개씩 `/api/timetable/study-progress`로 다시 채점했고, 행은 그 응답까지
 * 「—」와 꺼진 ▶로 기다렸다(운영 첫 묶음 2.8–5.5 s). 숫자 칸은 이미 `/api/root-learning`(useRootSummaries)에서
 * 오므로 목록에서는 부르지 않는다. 패널(EventPanel)은 강의 하나로 계속 부른다.
 */
const REFRESH_MS = 60_000;
export function useStudyTimetable(refreshKey: number, enabled: boolean) {
  const [events, setEvents] = useState<TimetableEvent[] | null>(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const lastLoaded = useRef(0);

  useEffect(() => {
    // 창에 돌아올 때마다 다시 읽지 않는다(2026-11-12). 캘린더처럼 60초에 한 번.
    const refresh = () => {
      if (document.visibilityState === "visible" && Date.now() - lastLoaded.current >= REFRESH_MS) setReload(old => old + 1);
    };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setError("");
    api<{ events: TimetableEvent[] }>("/api/timetable?include_study=false", { signal: controller.signal })
      .then(data => {
        if (controller.signal.aborted) return;
        setEvents(data.events);
        lastLoaded.current = Date.now();
      }).catch((cause: Error) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [refreshKey, reload, enabled]);

  return { events, setEvents, error };
}
