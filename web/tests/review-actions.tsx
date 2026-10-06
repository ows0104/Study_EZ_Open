// Vite /tests/review-actions.html: 실제 생성/전송 없이 관리자·학생 UI와 요청 자료를 확인한다.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import { PreviewAction } from "../src/calendar/PreviewAction";
import { ReviewAction } from "../src/calendar/ReviewAction";
import { BankPanel } from "../src/bank/BankPanel";
import type { LectureDetail, LectureRef } from "../src/types/lectures";
import "../src/styles/base.css";
import "../src/styles/calendar.css";

const query = new URLSearchParams(location.search);
const admin = !query.has("student");
if (!query.has("noextension")) document.documentElement.setAttribute("data-studyez-ai-extension", "1.3.5");
window.fetch = async (input) => {
  const path = new URL(String(input), location.origin).pathname;
  let payload: object = {};
  if (path.endsWith("/me")) payload = { isAdmin: admin, isApproved: true };
  else if (path.endsWith("/preview-prompt")) payload = { template: null };
  else if (path.endsWith("/timetable")) payload = { events: [] };
  else if (path.includes("/files/")) payload = { url: `http://localhost:8000/api/local-storage/lectures/${path.split("/").at(-1)}` };
  else if (path.endsWith("/prequiz-job")) payload = { job: null, runner: null };
  return new Response(JSON.stringify(payload), { status: 200 });
};
window.addEventListener("message", (event) => {
  if (event.data?.type !== "STUDYEZ_OPEN_PREVIEW") return;
  document.querySelector("#request")!.textContent = JSON.stringify(event.data.payload, null, 2);
  window.postMessage({ source: "studyez-ai-extension", type: "STUDYEZ_OPEN_PREVIEW_RESULT",
    requestId: event.data.payload.requestId, ok: true }, location.origin);
});
const detail = {
  subject: "약리학", runId: "261006_01", title: "약동학", course: "약리학", date: "2026-10-06", professors: ["담당 교수"],
  files: [
    { id: "previous", kind: "notes_prev", filename: "작년 강의록.pdf", sizeBytes: 1000 },
    { id: "current", kind: "notes_current", filename: "오늘 강의록.pdf", sizeBytes: 1000 },
    { id: "jokbo", kind: "jokbo", filename: "족보.pdf", sizeBytes: 1000 },
  ].filter(file => !query.has("nonotes") || file.kind !== "notes_current"),
  preview: null, myPreview: null,
  myReview: query.has("saved") ? { provider: "chatgpt", conversationUrl: "https://chatgpt.com/c/review" } : null,
  bank: { status: "ready", usable: true, open: true, questionCount: 30, conceptCount: 12 },
  bankSources: [{ assetId: "current", kind: "notes_current", filename: "오늘 강의록.pdf" }],
} as unknown as LectureDetail;
const lecture = { subject: detail.subject, runId: detail.runId } as LectureRef;
function Harness() {
  const [error, setError] = useState("");
  return <main style={{ maxWidth: 470, padding: 24, margin: "0 auto" }}>
    <h2>{admin ? "관리자" : "학생"} · 약동학</h2>
    <PreviewAction lecture={lecture} detail={detail} base="/api/lectures/약리학/261006_01" onError={setError} />
    <BankPanel lecture={lecture} detail={detail} />
    <ReviewAction lecture={lecture} detail={detail} base="/api/lectures/약리학/261006_01" onError={setError} />
    <details className="panel-hint legacy-main"><summary>기존 Main-Quiz 자료</summary><a href="#legacy">기존 카드 풀기</a></details>
    {error ? <p>{error}</p> : null}<pre id="request" style={{ whiteSpace: "pre-wrap" }} />
  </main>;
}
createRoot(document.getElementById("root")!).render(<Harness />);
