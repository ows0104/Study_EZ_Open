import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { DailyGoal } from "../src/bank/DailyGoal";
import type { LectureGoal } from "../src/types/studyPlan";
import "../src/styles/base.css";

function Preview() {
  const folded = new URLSearchParams(location.search).has("folded");
  const [value, setValue] = useState("progress");
  const plan: LectureGoal = {
    title: "콜린성 약리학", dayStart: 0, scope: "core",
    total: 12, completed: value === "complete" ? 12 : 8, remaining: value === "complete" ? 0 : 4,
    newRemaining: value === "complete" ? 0 : 2, reviewRemaining: value === "complete" ? 0 : 1,
    relearningRemaining: value === "complete" ? 0 : 1, waiting: 0, retryAt: null,
    firstPassSeen: value === "complete" ? 12 : 10, firstPassTotal: 12,
    progressPercent: value === "complete" ? 100 : 66,
    reviewedToday: value === "complete" ? 18 : 8, met: value === "complete",
  };
  return <main style={{ maxWidth: 620, margin: "30px auto", padding: 16 }}>
    <label>상태 <select value={value} onChange={e => setValue(e.target.value)}>
      <option value="progress">진행 중</option><option value="complete">강의 완료</option>
      <option value="missing">시험 미연결</option>
    </select></label>
    <div style={{ marginTop: 20 }}><DailyGoal plan={value === "missing" ? null : plan} showMain={!folded} collapsible={folded} /></div>
  </main>;
}

createRoot(document.getElementById("root")!).render(<Preview />);
