import { useCallback, useEffect, useRef, useState } from "react";
import { NOTE_READS_EVENT, type NoteReadsChange } from "./ReadEditor";
import { api } from "../api";
import { takeTimetable } from "../firstScreen";
import type { TimetableEvent } from "../types/lectures";
import { useOptionalVersion } from "../bank/optionalExclusion";

type Enriched = { events: TimetableEvent[] };
const inFlight = new Map<string, Promise<Enriched>>();

/**
 * 같은 범위의 학습률 요청이 진행 중이면 그것을 같이 기다린다. 목록을 기다리지 않고 마운트 즉시 보내므로
 * 다시 마운트되어도(개발 StrictMode·빠른 화면 전환) 서버 계산을 두 번 시키지 않는다. 끝나면 지워서 「다시 시도」는 새로 묻는다.
 */
function learning(url: string): Promise<Enriched> {
  let pending = inFlight.get(url);
  if (!pending) {
    pending = api<Enriched>(url);
    inFlight.set(url, pending);
    const clear = () => { if (inFlight.get(url) === pending) inFlight.delete(url); };
    pending.then(clear, clear);
  }
  return pending;
}

/**
 * 목록과 학습률(현재 격자 범위)을 **동시에** 읽는다(2026-11-12). 예전에는 목록이 온 뒤에야 학습률을 물어서
 * 두 요청 시간이 더해졌다. 먼저 온 쪽을 그리고, 늦게 온 쪽이 그 위에 덮는다.
 */
export function useCalendarTimetable(start: string, end: string, showLearning: boolean) {
  const [events, setEvents] = useState<TimetableEvent[] | null>(null);
  const [error, setError] = useState("");
  const [learningError, setLearningError] = useState("");
  const [learningLoading, setLearningLoading] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const lastLoaded = useRef(0);
  // 지금 범위의 학습률 응답(목록보다 먼저 오면 목록이 올 때 덮는다).
  const enriched = useRef<Map<string, TimetableEvent> | null>(null);
  const reload = useCallback(() => setRefreshVersion(old => old + 1), []);
  const optional = useOptionalVersion();  // Optional 계산 제외가 바뀌면 학습률을 다시 읽는다.

  useEffect(() => {
    let live = true;
    takeTimetable().then(data => {
      if (!live) return;
      const ready = enriched.current;
      setEvents(ready ? data.events.map(e => ready.get(e.id) ?? e) : data.events); setError("");
      lastLoaded.current = Date.now();
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
    enriched.current = null;
    if (!showLearning) { setLearningLoading(false); return; }
    let live = true;
    setLearningLoading(true);
    const query = new URLSearchParams({ start, end, include_cards: "false" });
    learning(`/api/timetable?${query}`)
      .then(data => {
        if (!live) return;
        const map = new Map(data.events.map(e => [e.id, e]));
        enriched.current = map;
        setEvents(old => old?.map(e => map.get(e.id) ?? e) ?? null);
      }).catch((cause: Error) => { if (live) setLearningError(cause.message); })
      .finally(() => { if (live) setLearningLoading(false); });
    return () => { live = false; };
  }, [start, end, showLearning, refreshVersion, optional]);

  // 패널에서 회독을 더하거나 지우면 칸의 회독 줄도 바로 바꾼다.
  useEffect(() => {
    const onReads = (event: Event) => {
      const { subject, runId, count } = (event as CustomEvent<NoteReadsChange>).detail;
      setEvents(old => old?.map(e => e.lectures.some(l => l.subject === subject && l.runId === runId)
        ? { ...e, lectures: e.lectures.map(l => l.subject === subject && l.runId === runId ? { ...l, noteReads: count } : l) }
        : e) ?? null);
    };
    window.addEventListener(NOTE_READS_EVENT, onReads);
    return () => window.removeEventListener(NOTE_READS_EVENT, onReads);
  }, []);

  return { events, error, learningError, learningLoading, reload };
}
