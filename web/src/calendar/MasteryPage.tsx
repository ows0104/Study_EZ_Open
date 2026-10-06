import { useEffect, useState } from "react";
import { api } from "../api";
import { takeTimetable } from "../firstScreen";
import type { TimetableEvent } from "../types/lectures";
import { MasteryBoard } from "./MasteryBoard";
import { StudyPlanBoard } from "./StudyPlanBoard";

/** 캘린더와 분리된 학습 현황. 풀이 창에서 돌아오면 최신 기록을 읽는다. */
export function MasteryPage() {
  const [events, setEvents] = useState<TimetableEvent[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const previousTitle = document.title;
    document.title = "학습도 · Study_EZ";
    let live = true;
    let request = 0;
    function load(initial = false) {
      const current = ++request;
      (initial ? takeTimetable() : api<{ events: TimetableEvent[] }>("/api/timetable"))
        .then(payload => {
          if (live && current === request) { setEvents(payload.events); setError(""); }
        })
        .catch((cause: Error) => { if (live && current === request) setError(cause.message); });
    }
    const refresh = () => load();
    load(true);
    window.addEventListener("focus", refresh);
    return () => {
      live = false;
      window.removeEventListener("focus", refresh);
      document.title = previousTitle;
    };
  }, []);

  return <div className="mastery-page">
    <h1>학습도</h1>
    <StudyPlanBoard />
    {error ? <p className="notice is-error">{error}</p>
      : events ? <MasteryBoard events={events} />
      : <p className="notice" role="status">강의별 학습도를 불러오는 중…</p>}
  </div>;
}
