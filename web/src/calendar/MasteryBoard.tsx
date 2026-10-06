import { useState } from "react";
import { bankHref, bankWindow, lectureHref } from "../links";
import { MasteryBadge } from "../lecture/LectureMastery";
import type { TimetableEvent } from "../types/lectures";

export function MasteryBoard({ events }: { events: TimetableEvent[] }) {
  const [filter, setFilter] = useState("needs_review");
  const [expanded, setExpanded] = useState(false);
  const today = new Date().toLocaleDateString("sv-SE");
  const seen = new Set<string>();
  const rows = events.filter(e => e.date <= today).flatMap(event => event.lectures.map(lecture => ({ event, lecture })))
    .filter(({ lecture }) => {
      const key = JSON.stringify([lecture.subject, lecture.runId]);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  // 구 API에서는 이 기능 전체를 숨긴다.
  if (!rows.some(({ lecture }) => lecture.mastery !== undefined)) return null;
  const needs = rows.filter(({ lecture: { mastery: m } }) => m && m.status !== "mastered");
  const pending = rows.filter(({ lecture }) => lecture.mastery === null).length;
  const filtered = (filter === "all" ? rows : needs).slice().sort((a, b) =>
    (a.lecture.mastery?.score ?? 101) - (b.lecture.mastery?.score ?? 101)
    || a.event.date.localeCompare(b.event.date) || a.lecture.title.localeCompare(b.lecture.title));
  return <section className="mastery-board" aria-label="강의별 학습도">
    <div className="mastery-heading">
      <h2>강의별 학습도</h2>
      <label>보기 <select value={filter} onChange={e => { setFilter(e.target.value); setExpanded(false); }}>
        <option value="needs_review">학습 부족 {needs.length}강의</option>
        <option value="all">전체 {rows.length}강의</option>
      </select></label>
    </div>
    <p className="mastery-caption">오늘까지의 강의 · 내 Quiz Bank 학습도 낮은 순 · 평가 준비 전 {pending}강의</p>
    {filtered.length ? <ul className="mastery-list">
      {(expanded ? filtered : filtered.slice(0, 5)).map(({ lecture, event }) => <li key={JSON.stringify([lecture.subject, lecture.runId])}>
        <div>
          <a href={lectureHref(lecture)} target="_blank" rel="noreferrer">{lecture.title}</a>
          <small>{event.date} · {lecture.subject}
            {lecture.mastery ? ` · 부족한 개념 ${lecture.mastery.weakConcepts}/${lecture.mastery.conceptCount}개` : ""}</small>
        </div>
        <div className="mastery-row-actions">
          <MasteryBadge value={lecture.mastery} />
          {lecture.mastery ? <a href={bankHref(lecture)} target={bankWindow(lecture)}>학습하기</a> : null}
        </div>
      </li>)}
    </ul> : <p>{rows.length > pending ? "평가 가능한 강의의 학습 목표를 모두 달성했습니다." : "평가할 문제가 아직 준비되지 않았습니다."}</p>}
    {filtered.length > 5 ? <button className="is-quiet" onClick={() => setExpanded(!expanded)}>
      {expanded ? "접기" : `${filtered.length}강의 모두 보기`}
    </button> : null}
  </section>;
}
