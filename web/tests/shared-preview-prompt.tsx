import { createRoot } from "react-dom/client";
import { PreviewAction } from "../src/calendar/PreviewAction";
import { MESSAGES, READY_ATTRIBUTE, WEBAPP_SOURCE, EXTENSION_SOURCE } from "../src/bridge/protocol";
import type { LectureDetail, LectureRef } from "../src/types/lectures";
import "../src/styles/base.css";
import "../src/styles/calendar.css";

const options = new URLSearchParams(location.search);
if (!options.has("noExtension")) document.documentElement.setAttribute(READY_ATTRIBUTE, "1.3.10");
const state = { stored: localStorage.getItem("test-shared-prompt") || "", requests: [] as string[], sent: [] as { mode: string; prompt: string }[], fail: false };
Object.assign(window, { promptTest: state });
window.fetch = async (input, init) => {
  const url = new URL(String(input), location.origin);
  state.requests.push(`${init?.method || "GET"} ${url.pathname}`);
  let result: object;
  if (url.pathname === "/api/me") result = { id: "test", isAdmin: !options.has("student"), isApproved: true };
  else if (url.pathname === "/api/admin/preview-prompt") {
    if (state.fail) return new Response(JSON.stringify({ detail: "저장 서버 오류" }), { status: 500 });
    if (init?.method === "PUT") {
      state.stored = JSON.parse(String(init.body)).prompt;
      localStorage.setItem("test-shared-prompt", state.stored);
    }
    result = { prompt: state.stored };
  } else if (url.pathname === "/api/me/preview-prompt") result = { prompt: "내 개인 프롬프트" };
  else if (url.pathname.endsWith("/files/notes")) result = { url: "/test.pdf" };
  else throw new Error(`Unexpected API: ${url.pathname}`);
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};
window.addEventListener("message", event => {
  if (event.data?.source === WEBAPP_SOURCE && event.data.type === MESSAGES.openPreview) {
    state.sent.push(event.data.payload);
    window.postMessage({ source: EXTENSION_SOURCE, type: MESSAGES.openPreviewResult, requestId: event.data.payload.requestId, ok: true }, location.origin);
  }
});
const lecture: LectureRef = {
  subject: "subject", runId: "run", title: "예시 강의", professors: ["교수"],
  marks: { notesPrev: true, notesCurrent: false, preview: false, prequiz: false, quiz: false },
  grabbed: { pre: false, main: false }, prequizProgress: null,
};
const detail: LectureDetail = {
  ...lecture, uid: "test", date: "2026-10-18", slot: 1, slotEnd: 1, startTime: "09:00", author: "", version: null, course: "과목",
  files: [{ id: "notes", kind: "notes_prev", filename: "작년 필기.pdf", label: "작년 필기", sizeBytes: 100 }],
  preview: null, myPreview: null, prequiz: null, mainquiz: null, bank: null,
};
createRoot(document.getElementById("root")!).render(<main style={{ maxWidth: 540, margin: "auto", padding: 16 }}>
  <PreviewAction lecture={lecture} detail={detail} base="/api/lectures/subject/run" onError={message => { throw new Error(message); }} />
</main>);
