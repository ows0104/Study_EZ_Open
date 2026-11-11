import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { bankCatalogHref, bankHref, lectureHref } from "../links";
import { useMe } from "../useMe";
import type { LectureRef, PreviewSource, TimetableEvent } from "../types/lectures";
import type { CardProgress } from "../types/mastery";
import { StudyPlanBoard } from "../calendar/StudyPlanBoard";
import { toCalendarEntries } from "../calendar/entries";
import { displayInfo, splitSubject, type DisplayKind } from "../calendar/kinds";
import { ProfTag } from "../calendar/ProfessorInfo";
import { Icon } from "../shell/icons";
import { BankBuildTimes } from "./BankBuildTimes";
import { useQuizPublication } from "./useQuizPublication";
import { QuizPublicationCell } from "./QuizPublicationCell";
import { currentStudyBlock, studyBlockKey, studyBlockNames, studyCourseOf } from "./studyBlocks";
import { useStudyCourse } from "./useStudyCourse";
import "./overview.css";
import { rootRate, useRootCatalog, useRootProgress } from "./useRootCatalog";
import type { RootQuestionProgress } from "../types/rootLearning";

// 캘린더와 같은 강의 패널. 행을 누를 때만 받는다.
const EventPanel = lazy(() => import("../calendar/EventPanel").then(m => ({ default: m.EventPanel })));

export type StudyLecture = Pick<LectureRef, "subject" | "runId" | "title" | "bankTimeline" | "mastery" | "cardProgress" | "studyLoaded"> & {
  date: string; course: string; ready: boolean; key: string; eventKey?: string;
  /** 모아풀기에 섞을 수 있는가(Quiz Bank). Main-Quiz만 있는 강의는 열리지만 섞이지 않는다. */
  batch?: boolean; mainQuiz?: boolean;
  /** 화면 계산값(2026-11 개편). DB에는 없다. */
  startTime?: string; kind?: DisplayKind; code?: string; professor?: string; field?: string;
  sources?: (PreviewSource | null | undefined)[];
};

const OTHER = "기타 강의";

function lectureRows(events: TimetableEvent[]): StudyLecture[] {
  const rows = new Map<string, StudyLecture>();
  const blocks = studyBlockNames(events);
  const infos = displayInfo(events);
  for (const event of toCalendarEntries(events)) {
    const course = blocks.get(studyBlockKey(studyCourseOf(event, events))) || OTHER;
    const info = infos.get(event.id);
    const split = splitSubject(event.detail);
    const shown = { startTime: event.startTime, kind: info?.kind, code: info?.code ?? "", professor: event.professor, field: split.subject };
    for (const l of event.lectures) {
      const key = `${l.subject}/${l.runId}`;
      // 캘린더 칸과 같은 제목: 한 칸에 강의 하나면 시간표 세부에서 분야 머리(「감염학)」)를 뗀 제목을 쓴다.
      const title = event.lectures.length === 1 ? split.title || l.title : l.title;
      if (!rows.has(key)) rows.set(key, { ...l, ...shown, title, sources: [l.previewSource], key, eventKey: `event:${event.id}`,
        date: event.date, course, ready: l.marks.quiz || Boolean(l.marks.mainQuiz), batch: l.marks.quiz,
        mainQuiz: Boolean(l.marks.mainQuiz) });
    }
    if (!event.lectures.length && ["lecture", "practice"].includes(event.category)) {
      const key = `event:${event.id}`;
      rows.set(key, { ...shown, sources: [], key, subject: event.course, course, runId: "", title: split.title || event.title,
        date: event.date, ready: false, batch: false });
    }
  }
  return [...rows.values()].sort((a, b) => a.date.localeCompare(b.date)
    || (a.startTime ?? "").localeCompare(b.startTime ?? "") || a.key.localeCompare(b.key));
}

/** 강의·실습·TBL/CBL을 처음부터 나눈다(2026-11-05 사용자 지시). TBL 영상은 TBL 쪽. */
const SECTIONS: { id: string; label: string; match: (kind?: DisplayKind) => boolean }[] = [
  { id: "lecture", label: "강의", match: kind => kind !== "practice" && kind !== "tbl" && kind !== "cbl" && kind !== "video" },
  { id: "practice", label: "실습", match: kind => kind === "practice" },
  { id: "group", label: "TBL·CBL", match: kind => kind === "tbl" || kind === "cbl" || kind === "video" },
];

/** 「기억 유지」는 「저장」으로 부른다(2026-11-06 사용자 결정). 서버 필드 `retained`는 그대로. */
const stages = [
  ["unseen", "미열람"], ["recognized", "인지"], ["retrieving", "인출"], ["retained", "저장"],
] as const;
const empty: CardProgress = { total: 0, seen: 0, unseen: 0, recognized: 0, retrieving: 0, retained: 0, newRemaining: 0, reviewDue: 0, suspended: 0 };
const number = (value: number) => value.toLocaleString("ko-KR");
const Num = ({ value }: { value: number }) => <span className={value ? undefined : "is-zero"}>{number(value)}</span>;

/** 학습률 25% 구간 색. 카드 단계 글자색과 같은 줄기. */
function rateBand(score: number) {
  if (score < 25) return "is-band1";
  if (score < 50) return "is-band2";
  if (score < 75) return "is-band3";
  return "is-band4";
}

const shortDate = (date: string) => date.slice(5).replace("-", ".");

type Block = { name: string; start: string; end: string };

function BlockPicker({ blocks, value, current, next, onChange }: {
  blocks: Block[]; value: string; current: string; next: string; onChange: (name: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const mark = (name: string) => name === current ? <span className="block-now">이번 블럭</span>
    : name === next ? <span className="block-now is-next">다음 블럭</span> : null;
  return <div className="block-picker">
    <button type="button" className="pill-button block-picker-button" data-block={value} aria-expanded={open} aria-haspopup="listbox"
      onClick={() => setOpen(old => !old)}>
      <span className="block-picker-label">블럭</span>{value || "—"}{mark(value)}<Icon.chevronDown />
    </button>
    {open ? <>
      <div className="block-scrim" onClick={() => setOpen(false)} />
      <div className="block-menu" role="listbox" aria-label="블럭"
        onKeyDown={e => { if (e.key === "Escape") setOpen(false); }}>
        {blocks.map(b => <button type="button" key={b.name} role="option" aria-selected={b.name === value}
          onClick={() => { onChange(b.name); setOpen(false); }}>
          <span className="block-menu-text"><b>{b.name}{mark(b.name)}</b><small>{shortDate(b.start)} – {shortDate(b.end)}</small></span>
          {b.name === value ? <Icon.check /> : null}
        </button>)}
      </div>
    </> : null}
  </div>;
}

function Check({ checked, label, disabled, onChange }: { checked: boolean; label: string; disabled?: boolean; onChange: (checked: boolean) => void }) {
  return <button type="button" role="checkbox" className="check" aria-checked={checked} aria-label={label} title={label}
    disabled={disabled} onClick={e => { e.stopPropagation(); onChange(!checked); }}>{checked ? <Icon.check /> : null}</button>;
}

/**
 * Main-Quiz 문항 수를 카드 열 모양으로. 단계 정의는 서버 `question_progress`(Quiz Bank `card_progress`와 같은 규칙).
 * 학습률은 아직 회상 가능 목표 비율이다(정의 통일은 대시보드 검토 요청 뒤).
 */
function fromRoot(q: RootQuestionProgress | undefined): CardProgress | null {
  return q ? { ...empty, ...q, seen: q.total - q.unseen } : null;
}

type ListView = "type" | "order";
const VIEW_KEY = "studyez-list-view";
function savedView(): ListView {
  try { return localStorage.getItem(VIEW_KEY) === "order" ? "order" : "type"; } catch { return "type"; }
}

/** 강의 목록: 블럭의 모든 강의와 카드 단계, 골라서 모아풀기. */
export function StudyOverview({ events, onStart, adminActions, hiddenKeys = [], onVisibility, managing = false, onDeleteQuiz, onScope }: {
  events: TimetableEvent[]; onStart: (lectures: StudyLecture[]) => void;
  adminActions?: (lectures: StudyLecture[]) => React.ReactNode;
  hiddenKeys?: string[]; onVisibility?: (keys: string[], hidden: boolean, count: number) => void; managing?: boolean;
  onDeleteQuiz?: (lectures: StudyLecture[]) => void;
  onScope?: (keys: string) => void;
}) {
  const isAdmin = Boolean(useMe()?.isAdmin);
  const navigate = useNavigate();
  const rows = useMemo(() => lectureRows(events), [events]);
  const hasMainQuiz = rows.some(l => l.mainQuiz);
  const roots = useRootCatalog(hasMainQuiz);
  const rootProgress = useRootProgress(hasMainQuiz);
  const entries = useMemo(() => toCalendarEntries(events), [events]);
  const infos = useMemo(() => displayInfo(events), [events]);
  const [view, setView] = useState<ListView>(savedView);
  const changeView = (next: ListView) => {
    setView(next);
    try { localStorage.setItem(VIEW_KEY, next); } catch { /* 이 탭에서만 유지 */ }
  };
  const [opened, setOpened] = useState<string | null>(null);
  const closePanel = useCallback(() => setOpened(null), []);
  /** Quiz Bank 카드 단계, 없으면 Main-Quiz 문항 단계. */
  const progressOf = (l: StudyLecture): CardProgress | null =>
    l.cardProgress ?? (l.mainQuiz ? fromRoot(rootProgress.get(l.key)) : null);
  const rateOf = (l: StudyLecture): number | null =>
    l.cardProgress ? l.mastery?.score ?? null : l.mainQuiz ? rootRate(roots.get(l.key)) : null;
  const [course, setCourse] = useStudyCourse(events);
  // useStudyCourse가 고른 기본 블럭과 같은 규칙. 블럭이 바뀌면 course도 바뀌므로 함께 다시 계산한다.
  const automatic = useMemo(() => currentStudyBlock(events), [events, course]);
  const [more, setMore] = useState(false);
  const [showPlan, setShowPlan] = useState(false);
  const [manageHidden, setManageHidden] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [managed, setManaged] = useState<Set<string>>(new Set());
  const hidden = new Set(hiddenKeys);
  const isHidden = (l: StudyLecture) => hidden.has(l.key) || Boolean(l.eventKey && hidden.has(l.eventKey));

  const blocks = useMemo(() => {
    const out = new Map<string, Block>();
    for (const l of rows) {
      const b = out.get(l.course);
      if (!b) out.set(l.course, { name: l.course, start: l.date, end: l.date });
      else { if (l.date < b.start) b.start = l.date; if (l.date > b.end) b.end = l.date; }
    }
    return [...out.values()].sort((a, b) => Number(a.name === OTHER) - Number(b.name === OTHER) || a.start.localeCompare(b.start));
  }, [rows]);
  const currentIndex = blocks.findIndex(b => b.name === automatic);
  const nextBlock = currentIndex >= 0 ? blocks.slice(currentIndex + 1).find(b => b.name !== OTHER)?.name ?? "" : "";
  const block = blocks.find(b => b.name === course);

  const inCourse = rows.filter(l => !course || l.course === course);
  const scoped = inCourse.filter(l => !isHidden(l));
  const scope = JSON.stringify(inCourse.filter(l => l.runId).map(l => l.key));
  useEffect(() => { onScope?.(scope); }, [scope, onScope]);
  const loading = scoped.some(l => l.studyLoaded === false);
  // 복습이 열린 강의만 센다. 아직 열리지 않은 강의까지 넣으면 미열람이 늘 대부분을 덮는다.
  const openedRows = scoped.filter(l => l.ready && progressOf(l));
  const totals = openedRows.reduce((sum, l) => {
    const p = progressOf(l)!;
    for (const key of Object.keys(empty) as (keyof CardProgress)[]) sum[key] += p[key];
    return sum;
  }, { ...empty });
  const rates = openedRows.map(rateOf).filter((r): r is number => r !== null);
  const score = rates.length ? Math.round(rates.reduce((sum, r) => sum + r, 0) / rates.length) : null;
  const display = (value: number) => loading ? "—" : number(value);

  const selectable = scoped.filter(l => l.batch);
  const chosen = selectable.filter(l => selected.has(l.key));
  const allPicked = selectable.length > 0 && selectable.every(l => selected.has(l.key));
  const pickedDue = chosen.reduce((sum, l) => sum + (l.cardProgress?.reviewDue ?? 0), 0);
  const toggle = (setter: typeof setSelected, keys: string[], checked: boolean) => setter(old => {
    const next = new Set(old);
    keys.forEach(key => checked ? next.add(key) : next.delete(key));
    return next;
  });

  const showProduction = inCourse.some(l => l.subject === "약리학");
  const production = useQuizPublication(more && showProduction);
  const productionById = new Map(production.values?.map(value => [value.runId, value]));
  const hiddenCount = inCourse.length - scoped.length;
  const manageRows = manageHidden ? inCourse.filter(isHidden) : scoped;
  const managedRows = manageRows.filter(l => managed.has(l.key));
  const deletable = managedRows.filter(l => l.bankTimeline?.deleteVersion);
  const manageable = manageRows.filter(l => onVisibility || l.ready);
  const allManaged = manageable.length > 0 && manageable.every(l => managed.has(l.key));
  const changeVisibility = (keys: string[], value: boolean) => {
    const affected = rows.filter(l => keys.includes(l.key));
    const savedKeys = value ? keys : [...new Set([...keys, ...affected.flatMap(l => l.eventKey ? [l.eventKey] : [])])];
    onVisibility?.(savedKeys, value, keys.length);
    toggle(setManaged, keys, false);
    toggle(setSelected, keys, false);
  };
  const changeBlock = (name: string) => { setCourse(name); setSelected(new Set()); setManaged(new Set()); };
  /** 복습 바로 풀기: Quiz Bank는 그 강의 하나로 모아풀기(시작 화면 없이), Main-Quiz는 오늘 계획으로 바로 회차. */
  const study = (l: StudyLecture) => l.batch ? onStart([l]) : navigate(`${bankHref(l)}?start=1`);

  // 행을 누르면 캘린더와 같은 패널. 행 key → 시간표 칸과 그 칸 안의 강의 순서.
  const openedRow = opened ? rows.find(l => l.key === opened) : undefined;
  const openedEntry = openedRow ? entries.find(e => `event:${e.id}` === (openedRow.eventKey ?? openedRow.key)) : undefined;
  const openedLecture = openedEntry && openedRow ? Math.max(0, openedEntry.lectures.findIndex(x => `${x.subject}/${x.runId}` === openedRow.key)) : 0;
  const groups = view === "order"
    ? [{ id: "order", label: "", list: scoped }]
    : SECTIONS.map(section => ({ id: section.id, label: section.label, list: scoped.filter(l => section.match(l.kind)) }));

  return <div className={`study-split${openedEntry ? " is-split" : ""}`}>
  <section className="study-overview">
    <header className="page-head list-head">
      <div><h1>강의 목록</h1>{block ? <p className="page-sub">{block.name} · {shortDate(block.start)} – {shortDate(block.end)}</p> : null}</div>
      <BlockPicker blocks={blocks} value={course} current={automatic} next={nextBlock} onChange={changeBlock} />
    </header>

    <div className="list-stats">
      <div><span>오늘 복습</span><b className="is-review">{display(totals.reviewDue)}<small>장</small></b></div>
      <div><span>학습률 평균</span><b>{loading || score === null ? "—" : `${score}%`}</b></div>
      <div><span>전체 카드</span><b>{display(totals.total)}<small>장</small></b></div>
    </div>
    <div className="stage-card">
      <div className="stage-legend">{stages.map(([key, label]) => <span key={key}>
        <i className={`stage-dot stage-${key}`} />{label}<b className={`stage-text-${key}`}>{display(totals[key])}</b></span>)}</div>
      <div className="stage-bar" role="img" aria-label={stages.map(([key, label]) => `${label} ${display(totals[key])}장`).join(" · ")}>
        {loading ? null : stages.map(([key]) => totals[key] > 0 ? <span key={key} className={`stage-${key}`} style={{ flex: totals[key] }} /> : null)}
      </div>
    </div>

    <div className="list-view more-tabs" role="group" aria-label="보기">
      <button type="button" aria-pressed={view === "type"} onClick={() => changeView("type")}>유형별</button>
      <button type="button" aria-pressed={view === "order"} onClick={() => changeView("order")}>순서대로</button>
    </div>

    <div className="list-table" role="table" aria-label="강의 목록">
      <div className="list-row is-head" role="row">
        <span role="columnheader"><Check checked={allPicked} label="열린 강의 모두 선택" disabled={managing || !selectable.length}
          onChange={checked => setSelected(checked ? new Set(selectable.map(l => l.key)) : new Set())} /></span>
        <span role="columnheader">번호</span>
        <span role="columnheader">강의</span>
        <span role="columnheader" className="is-num">전체</span>
        {stages.map(([key, label]) => <span role="columnheader" key={key} className="is-num is-stage"><i className={`stage-dot stage-${key}`} />{label}</span>)}
        <span role="columnheader" className="is-num">복습</span>
        <span role="columnheader" className="is-num">학습률</span>
        <span role="columnheader" className="list-go">복습 퀴즈</span>
      </div>
      {groups.map(group => {
        const list = group.list;
        if (!list.length) return null;
        return <div key={group.id} className="list-section" role="rowgroup" aria-label={group.label || "순서대로"}>
          {group.label ? <div className="list-section-title" role="row"><span role="cell">{group.label}<span>{list.length}</span></span></div> : null}
          {list.map(l => {
            const p = progressOf(l);
            const rate = rateOf(l);
            const picked = selected.has(l.key);
            const waiting = l.studyLoaded === false;
            const closed = waiting || !l.ready;
            const open = () => setOpened(l.key);
            return <div key={l.key} role="row" tabIndex={0} onClick={open}
              onKeyDown={e => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); open(); } }}
              className={`list-row is-link${picked ? " is-picked" : ""}${closed ? " is-closed" : ""}${opened === l.key ? " is-active" : ""}`}>
              <span role="cell" onClick={e => e.stopPropagation()}>
                {l.batch ? <Check checked={picked} label={`${l.title} 선택`} disabled={managing}
                  onChange={checked => toggle(setSelected, [l.key], checked)} /> : null}
              </span>
              <span role="cell" className="list-code">{l.code}</span>
              <span role="cell" className="list-title">
                <strong>{l.title}</strong>
                {l.professor || l.field ? <small>{l.professor}{l.professor ? <ProfTag values={l.sources ?? []} /> : null}
                  {l.professor && l.field ? " · " : ""}{l.field}</small> : null}
              </span>
              {!waiting && p ? <>
                <span role="cell" className="is-num"><Num value={p.total} /></span>
                {stages.map(([key]) => <span role="cell" key={key} className={`is-num is-stage stage-text-${key}`}><Num value={p[key]} /></span>)}
                <span role="cell" className={`is-num list-due${p.reviewDue ? " is-on" : ""}`}><Num value={p.reviewDue} /></span>
                <span role="cell" className={`is-num rate-text ${!l.ready ? "is-closed" : rate !== null ? rateBand(rate) : "is-closed"}`}>
                  {!l.ready ? "0%" : rate !== null ? `${rate}%` : "—"}</span>
              </> : waiting || l.ready ? <>
                <span role="cell" className="is-num">—</span>
                {stages.map(([key]) => <span role="cell" key={key} className="is-num is-stage">—</span>)}
                <span role="cell" className="is-num">—</span><span role="cell" className="is-num rate-text is-closed">—</span>
              </> : <>
                {/* 퀴즈 없음: 숫자 칸은 비우고 단추만 꺼 둔다. */}
                <span role="cell" className="is-num" />
                {stages.map(([key]) => <span role="cell" key={key} className="is-num is-stage" />)}
                <span role="cell" className="is-num" /><span role="cell" className="is-num" />
              </>}
              <span role="cell" className="list-go" onClick={e => e.stopPropagation()}>
                <button type="button" aria-label={`${l.title} 복습 퀴즈`} title="복습 퀴즈"
                  disabled={managing || waiting || !l.ready} onClick={() => study(l)}><Icon.play /></button>
              </span>
            </div>;
          })}
        </div>;
      })}
    </div>
    {!scoped.length ? <p className="list-empty">강의 없음</p> : null}

    {chosen.length ? <div className="pick-bar" role="region" aria-label="모아풀기">
      <span><b>{chosen.length}개 강의</b> 선택 · 오늘 복습 {number(pickedDue)}장</span>
      <span className="pick-spacer" />
      <button type="button" className="pick-clear" onClick={() => setSelected(new Set())}>선택 해제</button>
      <button type="button" className="pick-start" disabled={managing} onClick={() => onStart(chosen)}><Icon.play /> 모아풀기</button>
    </div> : null}

    <details className="list-more" onToggle={e => setMore(e.currentTarget.open)}>
      <summary>더 보기</summary>
      {more ? <>
        <section className="more-section" aria-label="강의 관리">
          <div className="more-toolbar">
            <h2>강의 관리</h2>
            {onVisibility ? <div className="more-tabs">
              <button type="button" aria-pressed={!manageHidden} onClick={() => { setManageHidden(false); setManaged(new Set()); }}>표시 {scoped.length}</button>
              <button type="button" aria-pressed={manageHidden} onClick={() => { setManageHidden(true); setManaged(new Set()); }}>숨긴 강의 {hiddenCount}</button>
            </div> : null}
            <label><input type="checkbox" checked={allManaged} disabled={managing || !manageable.length}
              onChange={e => toggle(setManaged, manageable.map(l => l.key), e.target.checked)} /> 표시된 강의 선택</label>
            {onVisibility ? <button className="is-quiet" disabled={!managedRows.length || managing}
              onClick={() => changeVisibility(managedRows.map(l => l.key), !manageHidden)}>
              선택 {managedRows.length}강의 {manageHidden ? "복원" : "숨기기"}</button> : null}
            {onDeleteQuiz ? <button className="is-quiet overview-delete" disabled={!deletable.length || managing}
              onClick={() => onDeleteQuiz(deletable)}>선택 퀴즈 삭제 ({deletable.length})</button> : null}
          </div>
          {showProduction ? <div className="quiz-production-note">
            <span><strong>퀴즈 준비 현황 · 10/15 이후</strong></span>
            <button className="is-quiet" onClick={production.refresh}>상태 새로고침</button>
            {production.error ? <small role="alert">상태 갱신 실패</small> : null}
          </div> : null}
          <div className="overview-table-wrap">
            <table className="overview-table">
              <caption className="sr-only">강의 관리</caption>
              <thead><tr><th scope="col">강의</th>{showProduction ? <><th scope="col">① 퀴즈 답변 · 링크<br /><small>10/15 이후</small></th>
                <th scope="col">② 완성 퀴즈 업로드<br /><small>10/15 이후</small></th></> : null}<th scope="col">관리</th></tr></thead>
              <tbody>{manageRows.map(l => <tr key={l.key} className={!l.ready ? "is-pending" : ""}>
                <th scope="row"><div className="overview-lecture">
                  <input type="checkbox" aria-label={`${l.title} 관리 선택`} disabled={managing || (!onVisibility && !l.ready)}
                    checked={managed.has(l.key)} onChange={e => toggle(setManaged, [l.key], e.target.checked)} />
                  <div>{l.runId ? <Link to={lectureHref(l)}>{l.title}</Link> : <span>{l.title}</span>}
                    <small>{[l.code, shortDate(l.date), l.subject].filter(Boolean).join(" · ")}</small>
                    {l.bankTimeline ? <details className="overview-materials"><summary>퀴즈 자료</summary>
                      <BankBuildTimes timeline={l.bankTimeline} />
                      {isAdmin && l.bankTimeline.shareUrl ? <a href={l.bankTimeline.shareUrl} target="_blank" rel="noreferrer">퀴즈뱅크 링크 ↗</a> : null}
                    </details> : null}
                  </div></div></th>
                {showProduction ? <><QuizPublicationCell value={productionById.get(l.runId)} kind="link" applicable={l.subject === "약리학"} />
                  <QuizPublicationCell value={productionById.get(l.runId)} kind="upload" applicable={l.subject === "약리학"} /></> : null}
                <td><div className="overview-row-actions">
                  {l.ready ? <Link to={bankCatalogHref(l)}>전체 문제</Link> : null}
                  {onVisibility ? <button className="is-quiet" disabled={managing} aria-label={`${l.title} ${isHidden(l) ? "복원" : "숨기기"}`}
                    onClick={() => changeVisibility([l.key], !isHidden(l))}>{isHidden(l) ? "복원" : "숨기기"}</button> : null}
                  {onDeleteQuiz && l.bankTimeline?.deleteVersion ? <button className="is-quiet overview-delete" disabled={managing}
                    aria-label={`${l.title} 퀴즈 삭제`} onClick={() => onDeleteQuiz([l])}>퀴즈 삭제</button> : null}
                </div></td>
              </tr>)}</tbody>
            </table>
          </div>
        </section>
        {adminActions ? <section className="more-section overview-admin" aria-label="선택 강의 관리">
          <h2>선택 강의 관리 <span>{chosen.length}</span></h2>{adminActions(chosen)}</section> : null}
        <details className="overview-plan" onToggle={e => setShowPlan(e.currentTarget.open)}>
          <summary>시험까지 · 오늘의 목표</summary>{showPlan ? <StudyPlanBoard /> : null}
        </details>
      </> : null}
    </details>
  </section>
  {openedEntry ? <Suspense fallback={<aside className="event-panel"><p role="status">강의 자료를 불러오는 중…</p>
    <button onClick={closePanel}>닫기</button></aside>}>
    <EventPanel key={`${openedEntry.id}/${openedLecture}`} entry={openedEntry} info={infos.get(openedEntry.id)}
      initialLecture={openedLecture} onClose={closePanel} />
  </Suspense> : null}
  </div>;
}
