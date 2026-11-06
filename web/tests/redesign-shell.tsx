/* 2026-11 UI 개편 확인용 고정물: 좌측 메뉴 + 캘린더 + 강의 목록 + 설정을 실제 컴포넌트로 띄운다.
 * 시간표는 data/timetable 의 11월 일정을 옮긴 redesign-shell-data.json, 학습 기록은 가짜 값이다.
 * 서버·운영 DB를 부르지 않는다. 열기: node web/node_modules/vite/bin/vite.js web → /tests/redesign-shell.html */
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { BankBatchPage } from "../src/bank/BankBatch";
import { CalendarPage } from "../src/calendar/CalendarPage";
import { startFirstScreen } from "../src/firstScreen";
import { SettingsPage } from "../src/settings/SettingsPage";
import { Sidebar } from "../src/shell/Sidebar";
import { applyAccent } from "../src/theme";
import type { LectureDetail, TimetableEvent } from "../src/types/lectures";
import data from "./redesign-shell-data.json";
import "../src/styles/base.css";
import "../src/styles/calendar.css";

const events = data as unknown as TimetableEvent[];
const hash = (text: string) => [...text].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);

function cards(runId: string, open: boolean) {
  const h = hash(runId);
  const total = 28 + (h % 30);
  if (!open) return { total, seen: 0, unseen: total, recognized: 0, retrieving: 0, retained: 0, newRemaining: total, reviewDue: 0, suspended: 0 };
  const seen = Math.min(total, 10 + (h % total));
  const retained = Math.floor(seen * ((h >>> 3) % 60) / 100);
  const retrieving = Math.floor((seen - retained) * 0.6);
  const recognized = seen - retained - retrieving;
  return { total, seen, unseen: total - seen, recognized, retrieving, retained, newRemaining: total - seen, reviewDue: (h % 9), suspended: 0 };
}

function detail(event: TimetableEvent): LectureDetail {
  const l = event.lectures[0];
  return {
    subject: l.subject, runId: l.runId, uid: event.id, title: l.title, date: event.date, slot: 1, slotEnd: 1,
    startTime: event.startTime, professors: l.professors, author: "", version: null, course: event.course,
    previewSource: null, files: [], preview: { provider: "chatgpt", shareUrl: "https://chatgpt.com/share/x" },
    myPreview: null, myReview: null,
    prequiz: l.prequizProgress ? { itemCount: l.prequizProgress.total, answered: l.prequizProgress.answered, correct: 0, new: 0, learning: 0, review: 0, later: 0, due: 0, nextDueAt: null } : null,
    mainquiz: null, mastery: l.mastery ?? null,
    bank: l.marks.quiz ? { usable: true, open: true, status: "ready", buildId: "b", questionCount: 40, studyQuestionCount: 40, seenQuestionCount: 12, conceptCount: 9, builtAt: null } : null,
    bankSources: [],
  } as unknown as LectureDetail;
}

window.fetch = async (input, init) => {
  const url = new URL(String(input), location.origin);
  let result: unknown;
  if (url.pathname === "/api/me") result = { id: "test", email: "student@studyez.kr", isAdmin: false, isApproved: true };
  else if (url.pathname === "/api/timetable") {
    // 실제 서버처럼 가벼운 목록에는 학습 정보가 없다(강의 목록이 이어서 study-progress를 부른다).
    result = { events: url.searchParams.get("include_study") === "false" && location.search.includes("/study")
      ? events.map(e => ({ ...e, lectures: e.lectures.map(l => ({ ...l, studyLoaded: false })) })) : events };
  }
  else if (url.pathname === "/api/timetable/study-progress") {
    const body = JSON.parse(String(init?.body ?? "{}")) as { lectures: { subject: string; runId: string }[] };
    result = { lectures: body.lectures.map(l => {
      const e = events.find(x => x.lectures[0]?.runId === l.runId);
      const lec = e?.lectures[0];
      return { ...l, ready: Boolean(lec?.marks.quiz), mastery: lec?.mastery ?? null, cardProgress: cards(l.runId, Boolean(lec?.marks.quiz)) };
    }) };
  } else if (url.pathname.startsWith("/api/me/study-hidden")) result = { keys: [] };
  else if (url.pathname.startsWith("/api/me/")) result = {};
  else if (url.pathname.endsWith("/deck-job") || url.pathname.endsWith("/prequiz-job")) result = { job: null, runner: null };
  else if (url.pathname.startsWith("/api/lectures/")) {
    const e = events.find(x => x.lectures[0] && url.pathname.endsWith(encodeURIComponent(x.lectures[0].runId)));
    if (!e) throw new Error(`Unexpected test API ${url.pathname}`);
    result = detail(e);
  } else result = {};
  return new Response(JSON.stringify(result), { headers: { "Content-Type": "application/json" } });
};

applyAccent();
startFirstScreen(true);
const start = new URLSearchParams(location.search).get("path") ?? "/";
createRoot(document.getElementById("root")!).render(
  <MemoryRouter initialEntries={[start]}>
    <div className="app-shell">
      <Sidebar email="student@studyez.kr" isAdmin={false} unseenNotice onSignOut={() => {}} />
      <div className="app-column">
        <main className="app-main is-wide">
          <Routes>
            <Route path="/" element={<CalendarPage />} />
            <Route path="/study" element={<BankBatchPage />} />
            <Route path="/settings" element={<SettingsPage email="student@studyez.kr" onSignOut={() => {}} />} />
            <Route path="*" element={<p className="notice">고정물에 없는 화면</p>} />
          </Routes>
        </main>
      </div>
    </div>
  </MemoryRouter>,
);
