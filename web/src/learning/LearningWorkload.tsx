import { useState } from "react";
import { Link } from "react-router-dom";
import type { LearningDashboard, LearningProgress, LearningWorkload } from "../types/learning";

export const learningUnit = (p: LearningProgress) => !p.legacyObjectives ? "요점"
  : p.legacyObjectives === p.total ? "문항" : "개";
const date = (at: number) => new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", month: "long", day: "numeric" }).format(at);
const fallback = (p: LearningProgress): LearningWorkload => ({ unseen: Math.max(0, p.total - p.covered), dueReviews: 0,
  nextReviewAt: null, firstPassTargetAt: null, examAt: null, today: null });

function Today({ value }: { value: LearningWorkload["today"] }) {
  if (!value) return <><strong>오늘 분량 확인 중</strong><small>전체 학습에서 오늘 계획을 확인하세요.</small></>;
  return <><strong>{value.remaining ? `오늘 남은 ${value.remaining}개` : value.deferred ? "오늘 공부 시간 마침"
    : value.total ? "오늘 분량 완료" : "오늘 배정 없음"}</strong>
    {value.remaining ? <span className="learning-counts"><span>새 내용 {value.new}</span><span>복습 {value.review}</span></span> : null}
    <small>{value.total ? `${value.completed} / ${value.total}개 완료` : "추가 학습으로 더 공부할 수 있어요."}
      {value.deferred ? ` · 미완료 ${value.deferred}개는 남아 있어요.` : ""}</small></>;
}

export function WorkloadSummary({ dashboard }: { dashboard: LearningDashboard }) {
  const p = dashboard.progress, w = dashboard.workload ?? fallback(p), unit = learningUnit(p);
  return <section aria-label="남은 학습량" className="learning-workload-summary">
    <article><span>첫 회독까지</span><strong>{w.unseen ? `${w.unseen}${unit} 남음` : p.total ? "첫 회독 완료" : "학습 자료 준비 중"}</strong>
      <small>공부한 {p.covered} / 전체 {p.total}{unit}</small>
      <progress aria-label="첫 회독 진행" value={p.covered} max={Math.max(1, p.total)} /></article>
    <article><span>오늘 할 분량</span><Today value={w.today} /></article>
    <article><span>기억 유지</span><strong>{dashboard.workload ? `지금 복습 ${w.dueReviews}${unit}` : "복습 일정 확인 중"}</strong>
      <small>{w.nextReviewAt ? `다음 복습 ${date(w.nextReviewAt)}` : "복습 날짜가 되면 할 분량에 포함해요."}</small></article>
  </section>;
}

type Filter = "all" | "today" | "unseen" | "review";
export function LectureWorkload({ lectures, scoped }: { lectures: LearningDashboard["lectures"]; scoped: boolean }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const visible = lectures.filter(l => `${l.title} ${l.subject}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())
    && (filter === "all" || (filter === "today" ? (l.workload?.today?.remaining ?? 0) > 0
      : filter === "unseen" ? l.covered < l.total : (l.workload?.dueReviews ?? 0) > 0)));
  return <section className="learning-panel learning-lecture-workload" aria-label="강의별 남은 학습량">
    <h2>{scoped ? "이 강의의 목표와 남은 분량" : "강의별 목표와 남은 분량"}</h2>
    <p className="learning-muted">첫 목표는 제공된 학습 범위를 한 번씩 공부하는 거예요. 첫 회독 뒤에도 간격에 맞춰 복습합니다.
      같은 내용을 반복해도 첫 회독 수는 늘지 않아요.</p>
    {!scoped ? <div className="learning-lecture-tools"><label>강의 찾기 <input value={search} onChange={e => setSearch(e.target.value)} placeholder="강의명이나 과목" /></label>
      <div className="learning-actions" aria-label="강의 목록 필터">{([["all", "전체"], ["today", "오늘 남음"], ["unseen", "첫 회독 남음"], ["review", "복습 필요"]] as const).map(([key, label]) =>
        <button key={key} aria-pressed={filter === key} onClick={() => setFilter(key)}>{label}</button>)}</div></div> : null}
    <div className="learning-lecture-list">{visible.map(l => {
      const w = l.workload ?? fallback(l), unit = learningUnit(l);
      return <article key={`${l.subject}/${l.runId}`} className="learning-lecture-card">
        <header><div><small>{l.subject}</small><h3><Link to={`/bank/${encodeURIComponent(l.subject)}/${encodeURIComponent(l.runId)}`}>{l.title}</Link></h3></div>
          <span className={`learning-first-pass-status${w.unseen ? "" : " is-complete"}`}>{w.unseen ? "첫 회독 중" : "첫 회독 완료"}</span></header>
        <div className="learning-lecture-counts"><div><span>처음 공부한 범위</span><strong>{l.covered} / {l.total}{unit}</strong>
          <progress aria-label={`${l.title} 첫 회독 진행`} value={l.covered} max={Math.max(1, l.total)} />
          <small>{w.unseen ? `아직 안 본 ${w.unseen}${unit}` : "제공된 학습 범위를 한 번씩 확인했어요."}</small></div>
          <div><span>오늘 할 분량</span><Today value={w.today} /></div></div>
        <p className="learning-lecture-goal">{w.firstPassTargetAt ? `첫 회독 목표 ${date(w.firstPassTargetAt)}${w.examAt ? ` · 시험 ${date(w.examAt)}` : ""}` : "첫 회독 목표 · 전체 범위를 한 번씩 공부하기"}</p>
        <footer><span>{l.workload ? `지금 복습할 ${w.dueReviews}${unit}` : "복습 일정 확인 중"}{w.nextReviewAt ? ` · 다음 복습 ${date(w.nextReviewAt)}` : ""}</span>
          <Link to={`/bank/${encodeURIComponent(l.subject)}/${encodeURIComponent(l.runId)}`}>강의 공부하기 →</Link></footer>
        {l.questionGaps ? <small className="learning-muted">{l.questionGaps}{unit}은 문제가 준비되지 않아 설명으로 공부해요.</small> : null}
        {l.legacyObjectives ? <small className="learning-muted">기존 자료는 문항별로 셉니다. 강의 전체 범위는 새 요점 목록이 준비되면 확인할 수 있어요.</small> : null}
      </article>;
    })}</div>
    {!visible.length ? <p>{lectures.length ? "이 조건에 맞는 강의가 없어요." : "공개된 학습 자료가 준비되면 강의별 분량을 보여 드려요."}</p> : null}
  </section>;
}
