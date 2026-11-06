import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { currentStudyBlock, studyBlockKey, studyCourseOf } from "../bank/studyBlocks";
import type { CardProgress } from "../types/mastery";
import type { TimetableEvent } from "../types/lectures";

type Progress = { subject: string; runId: string; cardProgress?: CardProgress | null };

/**
 * 「오늘」 줄의 「미열람 복습 퀴즈 n문제」(2026-11 개편): 이번 블럭 강의들의 오늘 복습할 카드 합.
 * 첫 화면 요청(`/api/me`, `/api/timetable?include_study=false`)이 끝난 뒤에만 따로 묻는다.
 * 강의 목록과 같은 `/api/timetable/study-progress`를 8강의씩 부른다. 실패하면 숫자를 비워 둔다.
 */
export function useTodayDue(events: TimetableEvent[] | null) {
  const lectures = useMemo(() => {
    if (!events?.length) return [];
    const block = studyBlockKey(currentStudyBlock(events));
    const seen = new Map<string, { subject: string; runId: string }>();
    for (const event of events) {
      if (studyBlockKey(studyCourseOf(event, events)) !== block) continue;
      for (const l of event.lectures) if (l.marks.quiz) seen.set(`${l.subject}/${l.runId}`, { subject: l.subject, runId: l.runId });
    }
    return [...seen.values()];
  }, [events]);
  const key = lectures.map(l => `${l.subject}/${l.runId}`).join(",");
  const [due, setDue] = useState<number | null>(null);

  useEffect(() => {
    if (!lectures.length) { setDue(null); return; }
    const controller = new AbortController();
    void (async () => {
      let total = 0;
      try {
        for (let offset = 0; offset < lectures.length; offset += 8) {
          const data = await api<{ lectures: Progress[] }>("/api/timetable/study-progress", {
            method: "POST", signal: controller.signal,
            body: JSON.stringify({ lectures: lectures.slice(offset, offset + 8) }),
          });
          if (controller.signal.aborted) return;
          total += data.lectures.reduce((sum, l) => sum + (l.cardProgress?.reviewDue ?? 0), 0);
        }
        setDue(total);
      } catch {
        if (!controller.signal.aborted) setDue(null);
      }
    })();
    return () => controller.abort();
    // 강의 묶음이 바뀔 때만 다시 센다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return due;
}
