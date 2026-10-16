import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { LectureRef, TimetableEvent } from "../types/lectures";

type Progress = Pick<LectureRef, "subject" | "runId" | "mastery" | "cardProgress"> & { ready: boolean };

/** 목록은 먼저, 문제은행·학습 기록은 선택한 블록만 8강의씩 읽는다. */
export function useStudyTimetable(refreshKey: number, enabled: boolean) {
  const [events, setEvents] = useState<TimetableEvent[] | null>(null);
  const [generation, setGeneration] = useState(0);
  const [scope, setScope] = useState("[]");
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const onScope = useCallback((value: string) => setScope(value), []);

  useEffect(() => { if (!enabled) setScope("[]"); }, [enabled]);

  useEffect(() => {
    const refresh = () => setReload(old => old + 1);
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
        setGeneration(old => old + 1);
      }).catch((cause: Error) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [refreshKey, reload, enabled]);

  useEffect(() => {
    if (!enabled || !generation || !events) return;
    const controller = new AbortController();
    const wanted = new Set<string>(JSON.parse(scope));
    const pending = [...new Map(events.flatMap(e => e.lectures)
      .filter(l => l.studyLoaded === false && wanted.has(`${l.subject}/${l.runId}`))
      .map(l => [`${l.subject}/${l.runId}`, { subject: l.subject, runId: l.runId }])).values()];
    if (!pending.length) return;
    setError("");
    void (async () => {
      try {
        for (let offset = 0; offset < pending.length; offset += 8) {
          const data = await api<{ lectures: Progress[] }>("/api/timetable/study-progress", {
            method: "POST", signal: controller.signal,
            body: JSON.stringify({ lectures: pending.slice(offset, offset + 8) }),
          });
          if (controller.signal.aborted) return;
          const values = new Map(data.lectures.map(l => [`${l.subject}/${l.runId}`, l]));
          setEvents(old => old?.map(e => ({ ...e, lectures: e.lectures.map(l => {
            const value = values.get(`${l.subject}/${l.runId}`);
            return value ? { ...l, mastery: value.mastery, cardProgress: value.cardProgress,
              marks: { ...l.marks, quiz: value.ready }, studyLoaded: true } : l;
          }) })) ?? null);
        }
      } catch (cause) { if (!controller.signal.aborted) setError((cause as Error).message); }
    })();
    return () => controller.abort();
    // 각 응답은 events를 갱신한다. 새 목록·블록에서만 다시 시작한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [generation, scope, enabled]);

  return { events, setEvents, onScope, error };
}
