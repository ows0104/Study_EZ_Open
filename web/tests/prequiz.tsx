// Vite에서 /tests/prequiz.html을 연다. 모든 API를 메모리로 대체하는 수동 회귀 확인용.
import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import "../src/styles/base.css";

const concepts = ["핵심 용어", "설명의 중심", "두 개념의 차이", "간단한 적용", "오늘의 큰 그림", "다음 설명 예상"];
const completedPreview = new URLSearchParams(location.search).has("completed");
const extraPreview = new URLSearchParams(location.search).has("extras");
if (extraPreview) concepts.push("암기할 구분", "자주 쓰는 수치", "대표 예외", "기출 반복 개념", "헷갈리는 대응");
const items = concepts.map((name, index) => ({
  itemId: `c00${index + 1}`, qtype: "basic", stem: `한 문장으로 설명해 보세요: ${name}`,
  focus: "spine", cardType: "comparison", examHit: false, whyTags: ["basis"],
  hint: `예습의 ‘${name}’ 부분에서 사용한 기준을 떠올려 보세요.`, challenge: index === 5,
  studyTrack: index < 6 ? "core" : "extra",
  difficulty: index === 5 ? "challenge" : index < 3 || index >= 6 ? "basic" : "advanced",
  attempt: (completedPreview && index < 6 ? { correct: index !== 0 && index !== 5, state: "review", dueAt: null } : null) as object | null,
}));
const next = Object.fromEntries(["again", "hard", "good", "easy"].map((g) => [g, { days: 1, seconds: 86400 }]));
const history: { itemId: string; attempt: object | null }[] = [];
let grades = 0;
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  const body = init?.body ? JSON.parse(String(init.body)) : {};
  const item = items.find((entry) => entry.itemId === body.itemId);
  const reveal = (entry: typeof items[number]) => ({
    itemId: entry.itemId, answer: `읽은 내용을 자신의 말로 정리한다.`,
    explanation: "설명에 나온 기준을 짧은 사례와 연결하면 된다.",
    whyAsked: "이 기준을 알고 들으면 수업의 비교 설명을 따라가기 쉽다.",
    learningScope: `${concepts[items.indexOf(entry)]}: 기준 하나만 알면 충분하다.`,
    lectureFocus: `‘${concepts[items.indexOf(entry)]}’ 부분의 기준을 사례에 어떻게 적용하는지 들어보자.`,
    next, slideUrl: null, slideNo: null, sourceAnchor: "",
  });
  let result: object;
  if (path === "/api/me") result = { isAdmin: false };
  else if (path === "/api/lectures/local/demo") result = {
    title: "핵심 개념과 기전: 예습으로 준비하는 강의", subject: "local", course: "예시 과목", date: "2026-10-07", files: [],
    prequiz: { missed: items.filter((entry) => entry.studyTrack === "core" &&
    entry.attempt && !(entry.attempt as { correct: boolean }).correct).map((entry) => ({ ...entry, ...reveal(entry) })),
    extraMissed: items.filter((entry) => entry.studyTrack === "extra" &&
    entry.attempt && !(entry.attempt as { correct: boolean }).correct).map((entry) => ({ ...entry, ...reveal(entry) })) } };
  else if (path.endsWith("/reveal") && item) result = reveal(item);
  else if (path.endsWith("/check") && item) {
    history.push({ itemId: item.itemId, attempt: item.attempt });
    item.attempt = { correct: body.understood, state: "review", dueAt: null };
    result = { itemId: item.itemId, attempt: item.attempt, undoable: true, now: new Date().toISOString() };
    document.getElementById("requests")!.textContent = `이해 확인 요청 ${++grades}회`;
  } else if (path.endsWith("/undo")) {
    const last = history.pop()!;
    const restored = items.find((entry) => entry.itemId === last.itemId)!;
    restored.attempt = last.attempt;
    result = { ...reveal(restored), attempt: last.attempt, undoable: history.length > 0, now: new Date().toISOString() };
  } else if (path.endsWith("/prequiz")) result = { items, now: new Date().toISOString(), undoable: history.length > 0 };
  else throw new Error(`예상하지 못한 API: ${path}`);
  return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json" } });
};

const { QuizPage } = await import("../src/lecture/QuizPage");
createRoot(document.getElementById("root")!).render(
  <MemoryRouter initialEntries={["/prequiz/local/demo"]}>
    <Routes><Route path="/prequiz/:subject/:runId" element={<QuizPage kind="pre" />} /></Routes>
  </MemoryRouter>,
);
