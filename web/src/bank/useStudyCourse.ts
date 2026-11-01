import { useEffect, useMemo, useState } from "react";
import type { TimetableEvent } from "../types/lectures";
import { currentStudyBlock, selectedStudyCourse } from "./studyBlocks";

export function useStudyCourse(events: TimetableEvent[]) {
  const [now, setNow] = useState(() => new Date());
  const automatic = useMemo(() => currentStudyBlock(events, now), [events, now]);
  const [manual, setManual] = useState<{ block: string; course: string } | null>(null);
  useEffect(() => {
    const refresh = () => setNow(new Date());
    const visible = () => { if (document.visibilityState === "visible") refresh(); };
    const timer = window.setInterval(visible, 60_000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", visible);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", visible);
    };
  }, []);
  useEffect(() => {
    setManual(old => old && old.block !== automatic ? null : old);
  }, [automatic]);
  const course = selectedStudyCourse(automatic, manual);
  const selectCourse = (value: string) => setManual({ block: automatic, course: value });
  return [course, selectCourse] as const;
}
