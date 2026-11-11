import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { StudyOverview } from "../src/bank/StudyOverview";
import type { PreviewSource, TimetableEvent } from "../src/types/lectures";
import "../src/styles/base.css";
import "../src/styles/calendar.css";

// Local visual fixture for 강의 목록: no real account, API or study records. `?mobile` narrows the frame.
// 2026-11-11부터 학습률·문항 단계는 Main-Quiz 하나: /api/root-learning 목록의 summary.score·questionProgress.
// 숫자 0 이상 = Main-Quiz 학습률, -1 = 옛 Quiz Bank만 있는 강의(legacy, 학습률 「—」), null = 퀴즈 없음, -2 = 강의 없음.
const catalog: unknown[] = [];
const summary = (score: number) => ({ total: 20, learned: 10, recalled: 5, unseen: 10, unready: 0, importantUnseen: 0, newToday: 0,
  recallChange: 0, recallLearningChange: 0, recallTimeChange: 0, targets: [], score });
window.fetch = async input => {
  const url = String(input instanceof Request ? input.url : input);
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  return url.includes("/api/root-learning") ? json({ lectures: catalog, canManage: false }) : json({ detail: "fixture" }, 404);
};
const source = (extra: Partial<PreviewSource>): PreviewSource => ({ version: 1, year: 2026, currentProfessors: [], currentSource: "timetable",
  baselineYear: 2025, baselineProfessors: [], changed: true, newProfessor: false, status: "ok", reason: "", selected: null,
  coverage: { available: [], missing: [], incomplete: [], failed: [] }, ...extra });
const rows: [string, string, TimetableEvent["category"], string, string, string, number | null, number, PreviewSource | null][] = [
  // date, start, category, title, details, professor, mastery, cards due, previewSource
  ["2026-11-02", "09:00", "lecture", "감염과 면역 1", "감염학) 감염질환에 대한 접근", "김남중", 82, 0, null],
  ["2026-11-02", "10:00", "lecture", "감염과 면역 2", "감염학) 감염병의 병인론", "최은화", 61, 4, source({ selected: { year: 2023, filename: "", professors: [], sha256: "", sizeBytes: 0, match: "same" } })],
  ["2026-11-02", "11:00", "lecture", "감염과 면역 3", "감염학) 감염병의 진단", "김택수", 34, 9, null],
  ["2026-11-02", "14:00", "lecture", "감염과 면역 5", "<동영상 강의 시청>\n위장관 감염", "", 12, 0, null],
  ["2026-11-03", "09:00", "lecture", "감염과 면역 TBL 1", "감염학) 위장관감염, 피부연조직감염", "박완범", 18, 6, null],
  ["2026-11-04", "09:00", "lecture", "감염과 면역 6", "미생물학) 포도알균", "김범준", null, 0, source({ newProfessor: true })],
  ["2026-11-04", "13:00", "practice", "감염과 면역 실습 1", "병리학) 감염 병리 통합실습", "김지은", null, 0, null],
  ["2026-11-05", "09:00", "lecture", "감염과 면역 9", "미생물학) 사슬알균", "김범준", -1, 0, null],
  ["2026-11-06", "11:00", "lecture", "감염과 면역 15", "미생물학) 미코박테리움", "염진기", -2, 0, null],
];
const events: TimetableEvent[] = rows.map(([date, startTime, category, title, details, professor, score, due, previewSource], i) => {
  const main = score !== null && score >= 0;
  if (main) catalog.push({ subject: "감염과 면역", runId: String(i), revision: "fixture", title, policyReady: true, plan: null, sessionId: null,
    summary: summary(score), questionProgress: { total: 40, unseen: 6 + i, recognized: 8, retrieving: 14 - i, retained: 12, reviewDue: due } });
  return {
    id: String(i), date, startTime, endTime: "10:00", title, details, professor, category, course: title.replace(/\s*(TBL|실습)?\s*\d+$/, ""), slot: i,
    lectures: score === -2 ? [] : [{ title: details.replace(/^.*\)\s*|<[^>]*>\n?/g, ""), subject: "감염과 면역", runId: String(i), professors: [professor], grabbed: { pre: false, main: false },
      prequizProgress: null, previewSource,
      marks: { notesPrev: false, preview: false, prequiz: false, notesCurrent: false, quiz: score === -1, mainQuiz: main },
      cardProgress: null,
      mastery: main ? { status: "needs_review", score, scope: "main-quiz", targetCount: 10, fullTargets: 5, ratedTargets: 8 } : null,
    }],
  };
});
const mobile = new URLSearchParams(location.search).has("mobile");
createRoot(document.getElementById("root")!).render(<MemoryRouter><main style={{ padding: "28px 36px" }}>
  <div style={mobile ? { width: 358, maxWidth: "100%", margin: "0 auto" } : undefined}>
    <StudyOverview events={events} onStart={chosen => { document.getElementById("started")!.textContent = `${chosen.length}강의 학습 시작`; }} />
    <p id="started" role="status" />
  </div>
</main></MemoryRouter>);
