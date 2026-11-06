import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { CalendarPage } from "../src/calendar/CalendarPage";
import { startFirstScreen } from "../src/firstScreen";
import { renderPreviewPrompt } from "../src/lecture/previewPrompt";
import type { LectureDetail, PreviewSource, TimetableEvent } from "../src/types/lectures";
import "../src/styles/base.css";
import "../src/styles/calendar.css";

const cases = [
  { title: "동일 교수 강의", changed: false, fresh: false, year: 2025, status: "ok" },
  { title: "교수 변경 강의", changed: true, fresh: false, year: 2023, status: "ok" },
  { title: "신규 교수 강의", changed: true, fresh: true, year: 2025, status: "ok" },
  { title: "담당 확인 강의", changed: null, fresh: null, year: 2025, status: "needs_review" },
  { title: "기존 자료 강의", changed: null, fresh: null, year: 2025, status: "ok" },
];
const sources: (PreviewSource | null)[] = cases.map((c, i) => i === 4 ? null : ({
  version: 1, year: 2026, currentProfessors: i === 3 ? [] : ["김범준"], currentSource: "timetable",
  baselineYear: 2025, baselineProfessors: i === 0 ? ["김범준"] : ["방예지"],
  changed: c.changed, newProfessor: c.fresh, status: c.status as "ok" | "needs_review",
  reason: c.fresh ? "보유 최근 5년 동일 교수 필기 없음 · 작년 자료 사용"
    : i === 3 ? "교수/과거 자료 확인 필요 · 확인된 작년 자료 사용" : "동일 교수의 최신 보유 필기",
  coverage: { available: [2025, 2023, 2022, 2021], missing: [2024], incomplete: [], failed: [] },
  selected: { year: c.year, filename: `[${String(c.year).slice(2)}1101_01] ${c.title}.pdf`,
    professors: i === 2 ? ["방예지"] : ["김범준"], sha256: "a".repeat(64), sizeBytes: 10,
    match: i === 2 ? "different" : "same" },
  conversationNeedsReview: i === 1, attachmentNeedsReview: false,
}));
const events: TimetableEvent[] = cases.map((c, i) => ({
  id: `professor-${i}`, title: `감염과 면역 ${i + 1}`, details: c.title, date: `2026-11-0${i + 2}`,
  startTime: "09:00", endTime: "10:00", professor: i === 3 ? "" : "김범준", category: "lecture",
  course: "감염과 면역", slot: 1,
  lectures: [{ subject: "감염과 면역", runId: `26110${i + 2}_01`, title: c.title, professors: ["김범준"],
    previewSource: sources[i], studyLoaded: false, marks: { notesPrev: true, preview: i === 1,
      prequiz: false, notesCurrent: false, quiz: false }, grabbed: { pre: false, main: false }, prequizProgress: null }],
}));
function detail(index: number): LectureDetail {
  const e = events[index], source = sources[index];
  return { subject: "감염과 면역", runId: e.lectures[0].runId, uid: e.id, title: cases[index].title,
    date: e.date, slot: 1, slotEnd: 1, startTime: "09:00", professors: e.lectures[0].professors,
    author: "", version: null, course: e.course, previewSource: source,
    files: [{ id: `file-${index}`, kind: "notes_prev", label: "예습 필기", sizeBytes: 10,
      filename: source?.selected?.filename || "[251101_01] 기존 자료.pdf", contentType: "application/pdf" }],
    preview: index === 1 ? { provider: "chatgpt", shareUrl: "https://chatgpt.com/share/old-source" } : null,
    myPreview: null, myReview: null, prequiz: null, mainquiz: null, bank: null, bankSources: [],
  } as LectureDetail;
}
Object.assign(window, { professorPreviewTest: {
  prompt: () => renderPreviewPrompt("{파일명}\n{교수}", detail(1)),
} });
window.fetch = async (input) => {
  const url = new URL(String(input), location.origin);
  let result: object;
  if (url.pathname === "/api/me") result = { id: "test", isAdmin: false, isApproved: true };
  else if (url.pathname === "/api/timetable") result = { events };
  else if (url.pathname === "/api/timetable/study-progress") result = { lectures: [] };
  else if (url.pathname.startsWith("/api/lectures/")) {
    const index = events.findIndex(e => url.pathname.endsWith(e.lectures[0].runId));
    if (index >= 0) result = detail(index);
    else if (url.pathname.endsWith("/prequiz-job") || url.pathname.endsWith("/deck-job")) result = { job: null, runner: null };
    else throw new Error(`Unexpected test API ${url.pathname}`);
  } else throw new Error(`Unexpected test API ${url.pathname}`);
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};
startFirstScreen(true);
createRoot(document.getElementById("root")!).render(<MemoryRouter initialEntries={["/?date=2026-11-05"]}>
  <main style={{ padding: 16 }}><CalendarPage /></main>
</MemoryRouter>);
