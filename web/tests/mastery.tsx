// /tests/mastery.html — 실제 API 없이 상태별 표시·정렬·필터·좁은 화면 확인.
import React from "react";
import { createRoot } from "react-dom/client";
import { MasteryBoard } from "../src/calendar/MasteryBoard";
import { StudyPlanBoard } from "../src/calendar/StudyPlanBoard";
import { LectureMastery } from "../src/lecture/LectureMastery";
import type { LectureMastery as Mastery } from "../src/types/mastery";
import type { TimetableEvent } from "../src/types/lectures";
import "../src/styles/base.css";

window.fetch = async (input) => {
  const url = new URL(String(input), location.origin);
  if (url.pathname !== "/api/study-plan") throw new Error(`Unexpected API: ${url.pathname}`);
  const target = Number(url.searchParams.get("target") ?? 90);
  const netGain = (target - 40 * .925 ** 7) * (1 - .925) / (1 - .925 ** 7) - 3;
  return new Response(JSON.stringify({ asOf: 0, unmatchedExams: ["종합시험"], unassignedLectures: 0,
    plans: [{ examId: "sample", title: "약물의 이해 시험", examDate: "2026-10-20", examTime: "09:00",
      lectureCount: 24, newToday: 2, upcomingLectures: 4, unassessedLectures: 4,
      daysLeft: 10, dayStart: 0, horizon: 86_400_000, target, morningScore: 40,
      studyDeadline: Date.parse("2026-10-17T09:00:00+09:00"), learningDaysLeft: 7,
      bufferDays: 3, bufferPhase: false, assumedDailyRetention: .925, lateLectures: 1,
      currentScore: 43.5, projectedScore: 41.5, endTarget: 40 + netGain, netGain,
      forgettingLoss: 3, requiredGain: netGain + 3, earnedGain: 4.5,
      remainingGain: Math.max(0, netGain - 1.5), met: netGain <= 1.5, availableCeiling: 59.2,
      limitedByMaterials: false, progressPercent: 42, reviewedToday: 12 }],
  }), { headers: { "Content-Type": "application/json" } });
};

const weak: Mastery = { status: "needs_review", score: 43, scope: "core", conceptCount: 8,
  masteredConcepts: 2, weakConcepts: 6, assessedDirections: 7, totalDirections: 16,
  weakest: [{ conceptId: "c1", title: "수용체와 신호 전달" }, { conceptId: "c2", title: "약물의 작용 기전" }] };
const values: (Mastery | null)[] = [weak, { ...weak, status: "not_started", score: 0, masteredConcepts: 0,
  weakConcepts: 8, assessedDirections: 0 }, { ...weak, status: "mastered", score: 100, masteredConcepts: 8,
  weakConcepts: 0, assessedDirections: 16, weakest: [] }, null];
const events: TimetableEvent[] = values.map((mastery, i) => ({
  id: String(i), date: "2026-01-01", startTime: "09:00", endTime: "10:00", title: "예시 강의", details: "",
  professor: "", category: "lecture", course: "약리학", slot: 1,
  lectures: [{ subject: "약리학", runId: String(i), title: ["콜린성 약리학", "자율신경계의 이해", "약물 대사", "항균제의 작용"][i],
    professors: [], mastery, prequizProgress: null, grabbed: { pre: false, main: false },
    marks: { notesPrev: false, preview: false, prequiz: false, notesCurrent: true, quiz: true } }],
}));
createRoot(document.getElementById("root")!).render(<main style={{ maxWidth: 900, margin: "30px auto", padding: 16 }}>
  <StudyPlanBoard />
  <MasteryBoard events={events} />
  <LectureMastery value={weak} />
  <LectureMastery value={null} />
</main>);
