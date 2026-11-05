import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { bankCatalogHref, bankHref, lectureHref } from "../links";
import { useMe } from "../useMe";
import type { LectureRef, TimetableEvent } from "../types/lectures";
import type { CardProgress } from "../types/mastery";
import { StudyPlanBoard } from "../calendar/StudyPlanBoard";
import { toCalendarEntries } from "../calendar/entries";
import { BankBuildTimes } from "./BankBuildTimes";
import { useQuizPublication } from "./useQuizPublication";
import { QuizPublicationCell } from "./QuizPublicationCell";
import { studyBlockKey, studyBlockNames } from "./studyBlocks";
import { useStudyCourse } from "./useStudyCourse";
import "./overview.css";
import { RootOverviewPanel } from "./RootLearning";

export type StudyLecture = Pick<LectureRef, "subject" | "runId" | "title" | "bankTimeline" | "mastery" | "cardProgress" | "studyLoaded"> & {
  date: string; course: string; ready: boolean; key: string; eventKey?: string;
};

function lectureRows(events: TimetableEvent[]): StudyLecture[] {
  const rows = new Map<string, StudyLecture>();
  const blocks = studyBlockNames(events);
  for (const event of toCalendarEntries(events)) {
    const course = blocks.get(studyBlockKey(event.course || event.lectures[0]?.subject || event.title)) || "기타 강의";
    for (const l of event.lectures) {
      const key = `${l.subject}/${l.runId}`;
      if (!rows.has(key)) rows.set(key, { ...l, key, eventKey: `event:${event.id}`, date: event.date, course, ready: l.marks.quiz });
    }
    if (!event.lectures.length && ["lecture", "practice"].includes(event.category)) {
      const key = `event:${event.id}`;
      rows.set(key, { key, subject: event.course, course, runId: "", title: event.detail || event.title,
        date: event.date, ready: false });
    }
  }
  return [...rows.values()].sort((a, b) => a.date.localeCompare(b.date) || a.key.localeCompare(b.key));
}

const stages = [
  ["unseen", "미열람"], ["recognized", "인지"], ["retrieving", "인출"], ["retained", "기억 유지"],
] as const;
const empty: CardProgress = { total: 0, seen: 0, unseen: 0, recognized: 0, retrieving: 0, retained: 0, newRemaining: 0, reviewDue: 0, suspended: 0 };
const number = (value: number) => value.toLocaleString("ko-KR");

function StageBar({ value }: { value: CardProgress }) {
  return <div className="card-stage-bar" role="img" aria-label={stages.map(([key, label]) => `${label} ${value[key]}개`).join(" · ")}>
    {stages.map(([key]) => value[key] > 0 ? <span key={key} className={`stage-${key}`} style={{ flex: value[key] }} /> : null)}
  </div>;
}

/** One list for seeing every lecture, comparing progress, and starting mixed study. */
export function StudyOverview({ events, onStart, adminActions, hiddenKeys = [], onVisibility, managing = false, onDeleteQuiz, onScope }: {
  events: TimetableEvent[]; onStart: (lectures: StudyLecture[]) => void;
  adminActions?: (lectures: StudyLecture[]) => React.ReactNode;
  hiddenKeys?: string[]; onVisibility?: (keys: string[], hidden: boolean, count: number) => void; managing?: boolean;
  onDeleteQuiz?: (lectures: StudyLecture[]) => void;
  onScope?: (keys: string) => void;
}) {
  const isAdmin = Boolean(useMe()?.isAdmin);
  const rows = useMemo(() => lectureRows(events), [events]);
  const [course, setCourse] = useStudyCourse(events);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("date");
  const [showPlan, setShowPlan] = useState(false);
  const [showProgress, setShowProgress] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const hidden = new Set(hiddenKeys);
  const isHidden = (l: StudyLecture) => hidden.has(l.key) || Boolean(l.eventKey && hidden.has(l.eventKey));
  const inCourse = rows.filter(l => !course || l.course === course);
  const scoped = inCourse.filter(l => !isHidden(l));
  const showProduction = inCourse.some(l => l.subject === "약리학");
  const production = useQuizPublication(showProduction);
  const productionById = new Map(production.values?.map(value => [value.runId, value]));
  const hiddenCount = inCourse.length - scoped.length;
  const scope = JSON.stringify(showProgress ? inCourse.filter(l => l.runId).map(l => l.key) : []);
  useEffect(() => { onScope?.(scope); }, [scope, onScope]);
  const loading = scoped.filter(l => l.studyLoaded === false).length;
  const display = (value: number) => loading ? "—" : number(value);
  const totals = (showProgress ? scoped : []).reduce((sum, l) => {
    if (l.cardProgress) for (const key of Object.keys(empty) as (keyof CardProgress)[]) sum[key] += l.cardProgress[key];
    return sum;
  }, { ...empty });
  const assessed = showProgress ? scoped.filter(l => l.mastery) : [];
  const score = assessed.length ? Math.round(assessed.reduce((sum, l) => sum + l.mastery!.score, 0) / assessed.length) : null;
  const available = scoped.filter(l => l.ready).length;
  const visible = (filter === "hidden" ? inCourse.filter(isHidden) : scoped)
    .filter(l => `${l.title} ${l.date} ${l.subject}`.toLowerCase().includes(search.toLowerCase())
    && (filter === "all" || filter === "hidden" || filter === "review" && (l.cardProgress?.reviewDue ?? 0) > 0
      || filter === "new" && (l.cardProgress?.newRemaining ?? 0) > 0
      || (filter === "new" || filter === "review") && l.studyLoaded === false || filter === "pending" && !l.ready))
    .sort((a, b) => sort === "score" ? (a.mastery?.score ?? 101) - (b.mastery?.score ?? 101) || a.date.localeCompare(b.date)
      : sort === "review" ? (b.cardProgress?.reviewDue ?? 0) - (a.cardProgress?.reviewDue ?? 0) || a.date.localeCompare(b.date) : 0);
  const selectedRows = rows.filter(l => selected.has(l.key) && isHidden(l) === (filter === "hidden"));
  const chosen = selectedRows.filter(l => l.ready && !isHidden(l));
  const deletable = selectedRows.filter(l => l.bankTimeline?.deleteVersion);
  const selectable = visible.filter(l => onVisibility || l.ready);
  const allChecked = selectable.length > 0 && selectable.every(l => selected.has(l.key));
  const toggle = (keys: string[], checked: boolean) => setSelected(old => {
    const next = new Set(old);
    keys.forEach(key => checked ? next.add(key) : next.delete(key));
    return next;
  });
  const changeVisibility = (keys: string[], value: boolean) => {
    const affected = rows.filter(l => keys.includes(l.key));
    const savedKeys = value ? keys : [...new Set([...keys, ...affected.flatMap(l => l.eventKey ? [l.eventKey] : [])])];
    onVisibility?.(savedKeys, value, keys.length);
    toggle(keys, false);
  };

  return <section className="study-overview">
    <RootOverviewPanel lectureKeys={scoped.map(l=>l.key)}/>
    <header className="overview-heading">
      <div><h1>학습 현황</h1><p>블록의 모든 강의와 내 카드가 쌓이는 과정</p></div>
      <label>블록 <select value={course} onChange={e => setCourse(e.target.value)}>
        <option value="">전체 블록</option>
        {[...new Set(rows.map(l => l.course))].filter(Boolean).map(c => <option key={c}>{c}</option>)}
      </select></label>
    </header>
    <details className="overview-progress" open={showProgress}>
      <summary onClick={e => {
        e.preventDefault();
        setShowProgress(old => !old);
        if (showProgress) {
          onScope?.("[]");
          setFilter(old => ["new", "review"].includes(old) ? "all" : old); setSort("date");
        }
      }}>학습 현황 {showProgress ? "접기" : "보기"}</summary>
      {showProgress ? <>
    {loading ? <p className="bank-note" role="status">선택한 블록의 학습 현황을 불러오는 중… {inCourse.filter(l => l.runId && l.studyLoaded !== false).length} / {inCourse.filter(l => l.runId).length}강의</p> : null}
    <div className="overview-stats">
      <div><span>전체 강의</span><strong>{scoped.length}<small>강의</small></strong><small>{loading ? "학습 가능 여부 확인 중" : `학습 가능 ${available} · 준비 전 ${scoped.length - available}`}</small></div>
      <div><span>전체 카드</span><strong>{display(totals.total)}<small>개</small></strong><small>공개된 카드 · 제외 {display(totals.suspended)}개 별도</small></div>
      <div><span>본 카드</span><strong>{display(totals.seen)}<small>개</small></strong><small>열람률 {loading ? "—" : totals.total ? Math.round(totals.seen / totals.total * 100) : 0}%</small></div>
      <div><span>새 학습 남음</span><strong>{display(totals.newRemaining)}<small>개</small></strong><small>미열람 {display(totals.unseen)}개 포함</small></div>
      <div className="overview-review"><span>복습할 카드</span><strong>{display(totals.reviewDue)}<small>개</small></strong><small>오늘까지 예정 · 아직 평가 전</small></div>
      <div><span>평균 학습률</span><strong>{loading ? "—" : score ?? "—"}<small>{loading || score === null ? "" : "%"}</small></strong><small>평가 가능 {loading ? "—" : assessed.length}강의의 평균</small></div>
    </div>
    <div className="overview-flow">
      <div className="stage-legend">{stages.map(([key, label]) => <span key={key}><i className={`stage-${key}`} />{label} <b>{display(totals[key])}</b></span>)}</div>
      {!loading ? <StageBar value={totals} /> : null}
      <details className="overview-help"><summary>인지 → 인출 → 기억 유지 · 지표 기준</summary>
        <p>미열람은 한 번도 열지 않은 카드입니다. 인지는 열어 봤지만 아직 평가하지 않았거나 마지막 평가가 Again·Hard인 카드,
          인출은 마지막 평가가 Good·Easy인 카드입니다. 그중 서로 다른 한국 날짜에 두 번 이상 Good·Easy로 평가하고 현재 추정 숙련도가 목표 이상이면 기억 유지로 표시합니다.</p>
        <p>네 단계는 중복 없이 전체 카드를 나눕니다. 복습할 카드는 단계와 별개로, 오늘까지 예정된 복습 중 아직 오늘 평가하지 않은 카드입니다.
          새 학습은 열어만 보고 평가하지 않은 카드도 포함합니다. Optional도 카드 수에 포함하고 학습에서 제외한 카드는 따로 셉니다.</p>
        <p>학습률은 핵심 개념의 목표 대비 달성도를 반영한 기존 학습도입니다. 핵심 문항이 없으면 전체 개념을 사용합니다.
          열람률과 다르며, 시간이 지나면 망각 추정에 따라 내려갑니다. 평균은 평가 가능한 강의만 포함하고 준비 전 강의는 제외합니다.
          기억 유지는 학습 기록에 따른 추정 상태입니다.</p>
      </details>
    </div>
      </> : null}
    </details>
    <div className="overview-filters">
      <label>검색 <input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="강의명 · 날짜 · 과목" /></label>
      <label>보기 <select value={filter} onChange={e => setFilter(e.target.value)}>
        <option value="all">모든 강의</option>{showProgress ? <><option value="new">새 학습 남음</option><option value="review">복습할 카드 있음</option></> : null}<option value="pending">준비 전</option>
        {onVisibility ? <option value="hidden">숨긴 강의 ({hiddenCount})</option> : null}
      </select></label>
      <label>정렬 <select value={sort} onChange={e => setSort(e.target.value)}>
        <option value="date">강의 순서</option>{showProgress ? <><option value="score">학습률 낮은 순</option><option value="review">복습 많은 순</option></> : null}
      </select></label>
      <span>{visible.length} / {filter === "hidden" ? hiddenCount : scoped.length}강의{hiddenCount ? ` · 숨김 ${hiddenCount}` : ""}</span>
    </div>
    <div className="overview-selection">
      <label><input type="checkbox" checked={allChecked} disabled={managing || !selectable.length}
        onChange={e => toggle(selectable.map(l => l.key), e.target.checked)} /> 표시된 강의 선택</label>
      <button className="is-quiet" disabled={!selected.size || managing} onClick={() => setSelected(new Set())}>선택 해제</button>
      {filter !== "hidden" ? <button disabled={!chosen.length || managing} onClick={() => onStart(chosen)}>{chosen.length}강의 모아 풀기</button> : null}
      {onVisibility ? <button className="is-quiet" disabled={!selectedRows.length || managing}
        onClick={() => changeVisibility(selectedRows.map(l => l.key), filter !== "hidden")}>
        선택 {selectedRows.length}강의 {filter === "hidden" ? "복원" : "숨기기"}</button> : null}
      {onDeleteQuiz ? <button className="is-quiet overview-delete" disabled={!deletable.length || managing}
        onClick={() => onDeleteQuiz(deletable)}>선택 퀴즈 삭제 ({deletable.length})</button> : null}
      {chosen.some(l => !visible.includes(l)) ? <small>다른 보기에서 선택한 강의 포함</small> : null}
    </div>
    {filter === "hidden" ? <p className="bank-note">숨긴 강의는 위 집계와 모아 풀기에서 제외됩니다. 복원하면 기존 학습 기록으로 이어집니다.</p> : null}
    {showProduction ? <div className="quiz-production-note">
      <span><strong>퀴즈 준비 현황 · 10/15 이후</strong> (한국 시간, 10/15 포함)<small>직접 저장한 답변이 있으면 링크보다 우선합니다. 답변 저장 또는 공유 응답 작성 시각과 퀴즈 업로드 시각을 따로 표시합니다. 화면은 30초마다 갱신됩니다.</small></span>
      <button className="is-quiet" onClick={production.refresh}>상태 새로고침</button>
      {production.error ? <small role="alert">상태 갱신 실패 · 마지막 확인 결과를 표시합니다.</small> : null}
    </div> : null}
    <div className="overview-table-wrap">
      <table className="overview-table">
        <caption className="sr-only">전체 강의별 카드 상태와 학습률</caption>
        <thead><tr><th scope="col">강의</th>{showProduction ? <><th scope="col">① 퀴즈 답변 · 링크<br /><small>10/15 이후</small></th><th scope="col">② 완성 퀴즈 업로드<br /><small>10/15 이후</small></th></> : null}{showProgress ? <><th scope="col">전체</th><th scope="col">본 카드</th><th scope="col">미열람</th>
          <th scope="col">인지</th><th scope="col">인출</th><th scope="col">기억 유지</th><th scope="col">복습</th><th scope="col">학습률</th></> : null}<th scope="col">학습</th></tr></thead>
        <tbody>{visible.map(l => {
          const p = l.cardProgress;
          return <tr key={l.key} className={!l.ready ? "is-pending" : ""}>
            <th scope="row"><div className="overview-lecture"><input type="checkbox" aria-label={`${l.title} 선택`} disabled={managing || (!onVisibility && !l.ready)}
              checked={selected.has(l.key)} onChange={e => toggle([l.key], e.target.checked)} />
              <div>{l.runId ? <Link to={lectureHref(l)}>{l.title}</Link> : <span>{l.title}</span>}
                <small>{l.date} · {l.subject}{showProgress && l.studyLoaded === false ? " · 학습 현황 확인 중" : !l.ready ? " · 준비 전" : ""}</small>
                {showProgress && p ? <StageBar value={p} /> : null}
                {l.bankTimeline ? <details className="overview-materials"><summary>퀴즈 자료</summary>
                  <BankBuildTimes timeline={l.bankTimeline} />
                  {isAdmin && l.bankTimeline.shareUrl ? <a href={l.bankTimeline.shareUrl} target="_blank" rel="noreferrer">퀴즈뱅크 링크 ↗</a> : null}
                </details> : null}
                {onVisibility || onDeleteQuiz ? <div className="overview-row-actions">
                  {onVisibility ? <button className="is-quiet" disabled={managing} aria-label={`${l.title} ${isHidden(l) ? "복원" : "숨기기"}`}
                    onClick={() => changeVisibility([l.key], !isHidden(l))}>{isHidden(l) ? "복원" : "숨기기"}</button> : null}
                  {onDeleteQuiz && l.bankTimeline?.deleteVersion ? <button className="is-quiet overview-delete" disabled={managing}
                    aria-label={`${l.title} 퀴즈 삭제`} onClick={() => onDeleteQuiz([l])}>퀴즈 삭제</button> : null}
                </div> : null}
              </div></div></th>
            {showProduction ? <><QuizPublicationCell value={productionById.get(l.runId)} kind="link" applicable={l.subject === "약리학"} />
              <QuizPublicationCell value={productionById.get(l.runId)} kind="upload" applicable={l.subject === "약리학"} /></> : null}
            {showProgress ? <><td>{p ? number(p.total) : "—"}{p?.suspended ? <small>제외 {p.suspended}</small> : null}</td>
            <td>{p ? number(p.seen) : "—"}{p && p.total > 0 ? <small>{Math.round(p.seen / p.total * 100)}%</small> : null}</td>
            <td>{p ? number(p.unseen) : "—"}{p && p.newRemaining !== p.unseen ? <small>평가 전 {p.newRemaining}</small> : null}</td>
            <td>{p ? number(p.recognized) : "—"}</td><td>{p ? number(p.retrieving) : "—"}</td><td>{p ? number(p.retained) : "—"}</td>
            <td className={p?.reviewDue ? "has-review" : ""}>{p ? number(p.reviewDue) : "—"}</td>
            <td>{l.mastery ? <div className="overview-score"><strong>{l.mastery.score}%</strong><progress value={l.mastery.score} max={100} aria-label={`${l.title} 학습률`} /></div> : "—"}</td></> : null}
            <td>{l.ready ? <><Link to={bankHref(l)}>풀기 →</Link><small><Link to={bankCatalogHref(l)}>전체 문제</Link></small></> : <span className="overview-wait">준비 전</span>}</td>
          </tr>;
        })}</tbody>
      </table>
    </div>
    {!visible.length ? <p className="notice">조건에 맞는 강의가 없습니다.</p> : null}
    {adminActions ? <details className="overview-admin"><summary>선택 강의 관리</summary>{adminActions(chosen)}</details> : null}
    <details className="overview-plan" onToggle={e => setShowPlan(e.currentTarget.open)}>
      <summary>시험까지 · 오늘의 목표</summary>{showPlan ? <StudyPlanBoard /> : null}
    </details>
  </section>;
}
