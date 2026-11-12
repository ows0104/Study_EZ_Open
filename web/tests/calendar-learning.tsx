// 실제 격자로 학습도·미학습·준비 전·구 API·여러 강의·좁은 화면을 확인한다.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import { CalendarGrid } from "../src/calendar/CalendarGrid";
import { EventChip } from "../src/calendar/EventChip";
import type { CalendarEntry, CalendarMode } from "../src/calendar/entries";
import type { LectureRef } from "../src/types/lectures";
import type { LectureMastery } from "../src/types/mastery";
import "../src/styles/base.css";
import "../src/styles/calendar.css";

function lecture(score: number | null | undefined, id: string): LectureRef {
  const mastery: LectureMastery | null | undefined = score === undefined ? undefined : score === null ? null : {
    score, status: score === 0 ? "not_started" : score === 100 ? "mastered" : "needs_review",
    scope: "core", conceptCount: 8, masteredConcepts: score === 100 ? 8 : 0,
    weakConcepts: score === 100 ? 0 : 8, assessedDirections: score === 0 ? 0 : 7,
    totalDirections: 16, weakest: [],
  };
  return { subject: "약리학", runId: id, title: `예시 강의 ${id}`, professors: [], mastery,
    // Main-Quiz 없는 강의(score undefined)는 복습 막대가 없다(2026-11-12).
    marks: { notesPrev: true, preview: true, prequiz: id !== "4", notesCurrent: true, quiz: true, mainQuiz: score !== undefined },
    grabbed: { pre: true, main: true }, prequizProgress: id === "4" ? null : { answered: [0, 2, 3, 6, 0, 1, 6, 0, 3, 7][Number(id)] ?? 3, total: 6 } };
}

const entries: CalendarEntry[] = Array.from({ length: 10 }, (_, i) => ({
  id: String(i), title: "약리학", detail: ["자율신경계 약물의 작용 기전", "수용체와 신호 전달", "약물 대사와 배설", "항균제의 작용", "평가할 문제 없음"][i % 5],
  date: `2026-10-${String(5 + i % 5).padStart(2, "0")}`, startTime: i < 5 ? "09:00" : "11:00",
  endTime: i < 5 ? "10:00" : "13:00", professor: "담당 교수", category: "lecture", course: "약리학",
  lectures: [lecture([0, 49, 50, 100, null, undefined, 43, 0, null, 99.9][i], String(i))],
}));
entries[6].lectures.push(lecture(100, "second"), lecture(null, "third"));
entries[7].lectures = [];
entries[7].category = "exam";
entries[7].detail = "약리학 시험";
// TBL·Main-Quiz 없음: 아래 줄 자체가 없다. TBL·Main-Quiz 있음: 막대가 있다.
entries[4] = { ...entries[4], title: "약리학 TBL 1", detail: "약리학 TBL 1", lectures: [{ ...lecture(undefined, "4"), prequizProgress: null }] };
entries[9] = { ...entries[9], title: "약리학 TBL 2", detail: "약리학 TBL 2" };

function Harness() {
  const [mode, setMode] = useState<CalendarMode>("week");
  const [width, setWidth] = useState(1000);
  const [short, setShort] = useState(false);
  const [active, setActive] = useState("");
  return <main style={{ padding: 10 }}>
    <h1>캘린더 학습도 확인</h1>
    <div style={{ display: "flex", gap: 12, alignItems: "center", margin: "14px 0", flexWrap: "wrap" }}>
      <button onClick={() => setMode("week")}>주간</button><button onClick={() => setMode("month")}>월간</button>
      <label>화면 폭 <select value={width} onChange={e => setWidth(Number(e.target.value))}>
        <option value={1000}>넓은 화면</option><option value={700}>패널 열린 화면</option><option value={375}>모바일 375px</option>
      </select></label>
      <label><input type="checkbox" checked={short} onChange={e => setShort(e.target.checked)} /> 낮은 화면</label>
    </div>
    <div className="calendar-page" style={{ width }}>
      <div className="calendar-main" style={{ height: short ? 420 : 600 }}>
        <CalendarGrid mode={mode} anchorDate={new Date(2026, 9, 7)} entries={entries}
          renderEntry={(entry, compact) => <EventChip key={entry.id} entry={entry} compact={compact}
            active={active === entry.id} onOpen={entry => setActive(entry.id)} />} />
      </div>
    </div>
  </main>;
}
createRoot(document.getElementById("root")!).render(<Harness />);
