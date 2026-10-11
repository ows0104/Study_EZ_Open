import { useState } from "react";
import { Link } from "react-router-dom";
import type { LearningDashboard, LearningProgress, LearningWorkload } from "../types/learning";

export const learningUnit = (p: LearningProgress) => !p.legacyObjectives ? "요점"
  : p.legacyObjectives === p.total ? "문항" : "개";
export const learningDate = (at: number) => new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", month: "long", day: "numeric" }).format(at);
export const workloadOf = (p: LearningProgress): LearningWorkload => p.workload ?? ({ unseen: Math.max(0, p.total - p.covered), dueReviews: 0,
  nextReviewAt: null, firstPassTargetAt: null, examAt: null, today: null });

type Filter = "all" | "today" | "unseen" | "review";
export function LectureWorkload({ lectures }: { lectures: LearningDashboard["lectures"] }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const visible = lectures.filter(l => `${l.title} ${l.subject}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())
    && (filter === "all" || (filter === "today" ? (l.workload?.today?.remaining ?? 0) > 0
      : filter === "unseen" ? l.covered < l.total : (l.workload?.dueReviews ?? 0) > 0)));
  return <section id="learning-lectures" className="learning-lecture-picker" aria-label="강의별 공부 현황">
    <header><h2>강의 골라서 공부하기</h2><label><span className="sr-only">강의 찾기</span><input aria-label="강의 찾기" value={search} onChange={e => setSearch(e.target.value)} placeholder="강의명·과목 검색" /></label></header>
    <div className="learning-filters" aria-label="강의 목록 필터">{([["all", "전체"], ["today", "오늘 풀 것"], ["unseen", "처음 공부할 것"], ["review", "복습할 것"]] as const).map(([key, label]) =>
      <button key={key} aria-pressed={filter === key} onClick={() => setFilter(key)}>{label}</button>)}</div>
    <div className="learning-lecture-rows">{visible.map(l => {
      const w = workloadOf(l), unit = learningUnit(l), link = `/bank/${encodeURIComponent(l.subject)}/${encodeURIComponent(l.runId)}`;
      return <article key={`${l.subject}/${l.runId}`} className="learning-lecture-row">
        <div className="learning-lecture-name"><small>{l.subject}</small><h3><Link to={link}>{l.title}</Link></h3></div>
        <div className="learning-lecture-progress"><span>한 번 공부함 <b>{l.covered} / {l.total}{unit}</b></span>
          <progress aria-label={`${l.title} 공부한 범위`} value={l.covered} max={Math.max(1, l.total)} />
          <small>처음 공부할 {w.unseen}{unit} · {l.workload ? `복습할 ${w.dueReviews}${unit}` : "복습 일정 확인 중"}</small></div>
        <div className="learning-lecture-open"><small>{w.today?.remaining ? `오늘 ${w.today.remaining}개 남음` : w.today?.deferred ? `미완료 ${w.today.deferred}개` : ""}</small><Link to={link} aria-label={`${l.title} 강의 열기`}>강의 열기 →</Link></div>
      </article>;
    })}</div>
    {!visible.length ? <p className="learning-muted">{lectures.length ? "이 조건에 맞는 강의가 없어요." : "공부할 자료를 준비하고 있어요."}</p> : null}
  </section>;
}
