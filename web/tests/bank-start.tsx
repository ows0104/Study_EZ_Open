// Local preview of the real overview: new, partial, completed and legacy API states.
import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { StudyNav } from "../src/StudyNav";
import { BankStart } from "../src/bank/BankStart";
import type { BankConcept, BankRead } from "../src/types/bank";
import "../src/styles/base.css";

const titles = ["선형 약동학", "용량 의존 비선형성", "시간 의존 비선형성", "대사 포화", "흡수와 생체이용률",
  "분포 용적", "청소율", "반감기", "정상 상태", "부하 용량", "유지 용량", "치료 약물 농도",
  "신장 기능과 용량", "간 기능과 용량", "약물 상호작용", "효소 유도", "효소 억제", "개인별 용량 조절"];
function Preview() {
  const [state, setState] = useState("new");
  const [started, setStarted] = useState(false);
  const completed = state === "complete" ? 28 : state === "partial" ? 16 : 0;
  const concepts: BankConcept[] = titles.map((title, i) => ({
    concept_id: `C${i + 1}`, title, graph_title: title, tier: i === 17 ? "Optional" : "Core",
    importance: 5 - i % 4, concept_difficulty: 2, exam_signal_strength: "high",
    importance_rationale: "약물의 농도 변화를 이해하고 적절한 용량을 판단하는 데 필요합니다.",
    core_facts: ["용량과 약물 농도의 관계를 설명할 수 있다.", "환자의 특성에 맞춰 약물 투여 간격을 판단한다."],
    related_concepts: i ? [`C${i}`] : ["C4", "C8"],
    progress: state === "new" ? 0 : state === "complete" ? 1 : [0, .2, .6, 1][i % 4],
    directions: [{ direction: "direct", mastery: state === "new" ? 0 : state === "complete" ? .8 : [0, .16, .48, .8][i % 4],
      target: .8, reviews: state === "new" ? 0 : 3, questions: 2 }],
  }));
  const info: BankRead = {
    summary: { status: "ready", open: true, usable: true, buildId: "preview", questionCount: 60, conceptCount: 18, builtAt: null },
    examDate: "2026-10-20", sizes: [10, 20, 30], defaultSize: 20, session: null, previousSessions: [],
    conceptMap: state === "legacy" ? undefined : concepts,
    mastery: { status: "not_started", score: 0, scope: "core", conceptCount: 17, masteredConcepts: 0,
      weakConcepts: 17, assessedDirections: 0, totalDirections: 28, weakest: [{ conceptId: "C1", title: titles[0] }] },
    lectureGoal: { title: "약동학(3) 약물요법에의 통합적 적용", dayStart: 0, scope: "core", total: 28,
      completed, remaining: 28 - completed, newRemaining: 28 - completed, reviewRemaining: 0,
      relearningRemaining: 0, waiting: 0, retryAt: null, met: state === "complete", progressPercent: completed / 28 * 100,
      reviewedToday: completed, firstPassSeen: completed, firstPassTotal: 28 },
  };
  window.fetch = async (input, init) => {
    if (!String(input).endsWith("/session/start")) throw new Error("Unexpected preview API");
    document.getElementById("request")!.textContent = String(init?.body);
    return new Response("{}", { headers: { "Content-Type": "application/json" } });
  };
  return <>
    <StudyNav />
    <label>미리보기 상태 <select value={state} onChange={e => { setState(e.target.value); setStarted(false); }}>
      <option value="new">미학습</option><option value="partial">학습 중</option>
      <option value="complete">오늘 완료</option><option value="legacy">이전 API</option>
    </select></label>
    {started ? <p role="status">학습 시작 요청 확인</p> : null}
    <BankStart base="/preview/bank" info={info} lecture={{ subject: "약리학", runId: "preview" }} finished={null} onStarted={() => setStarted(true)} />
    <output id="request" />
  </>;
}
createRoot(document.getElementById("root")!).render(<MemoryRouter><Preview /></MemoryRouter>);
