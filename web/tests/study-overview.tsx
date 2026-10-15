import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { StudyOverview } from "../src/bank/StudyOverview";
import type { TimetableEvent } from "../src/types/lectures";
import "../src/styles/base.css";
const titles = ["약력학(1) · 수용체와 용량 반응", "약동학 · 흡수와 분포", "약물대사", "콜린성 약리학(1)", "중추신경계 약리 기초", "면역억제제"];
const events: TimetableEvent[] = titles.map((title, i) => ({
  id: String(i), title, date: `2026-10-${String(i+1).padStart(2,"0")}`, startTime: "09:00", endTime: "10:00", details: "", professor: "", category: "lecture", course: i < 5 ? "약리학" : "감염학", slot: i,
  lectures: i === 4 ? [] : [{ title, subject: i < 5 ? "약리학" : "감염학", runId: String(i), professors: [], grabbed: {pre:false, main:false}, prequizProgress: null,
    marks:{notesPrev:false,preview:false,prequiz:false,notesCurrent:false,quiz:i!==3},
    cardProgress: i===3 ? null : { total:100, seen:80, unseen:20, recognized:15, retrieving:40, retained:25, newRemaining:23, reviewDue: i ? 0 : 12, suspended:2 },
    mastery: i===3 ? null : {status:"needs_review",score:63+i*5,scope:"core",conceptCount:10,masteredConcepts:5,weakConcepts:5,assessedDirections:10,totalDirections:20,weakest:[]},
  }],
}));
function Harness() {
  return <MemoryRouter><main style={{margin:"24px auto", maxWidth:1400,padding:16}}>
    <div style={new URLSearchParams(location.search).has("mobile") ? {width:358,maxWidth:"100%",margin:"0 auto"}:undefined}>
      <StudyOverview events={events} onStart={chosen => { document.getElementById("started")!.textContent = `${chosen.length}강의 학습 시작`; }} />
      <p id="started" role="status" />
    </div>
  </main></MemoryRouter>;
}
createRoot(document.getElementById("root")!).render(<Harness />);
