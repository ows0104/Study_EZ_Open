import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { useNoteLecture } from "../notes/noteLecture";
import { Icon } from "../shell/icons";
import type { JokboBand, JokboDoc, JokboItem, JokboMark, JokboResponse } from "../types/jokbo";
import { JokboBody } from "./JokboBody";
import { RATINGS, postAnswer, putBand, shownBand, type Shown } from "./marks";
import {
  changedChoices, defaultScope, grade, needed, otherYears, pickItems, professorsOf, sameItemIds, yearsOf,
  type JokboScope, type Verdict,
} from "./selection";
import "../bank/main-quiz.css";
import "../lecture/prequiz.css";
import "./jokbo.css";

/**
 * 강의별 족보 퀴즈(2026-11-13 사용자 지시).
 *
 * 진입 화면에서 범위(같은 교수만 / 다른 교수까지 + 연도)를 고르고 **한 문제씩** 푼다.
 * 고르면 바로 정답·선지별 해설이 나온다.
 *
 * 2026-11-14 개편(사용자 「예습퀴즈 느낌」): 풀이·끝 화면을 예습 퀴즈 틀(머리줄·진행 막대·카드·아래 독)로.
 * 답을 본 뒤 독에서 **모르겠음 · 주의 · 괜찮음**을 골라야 넘어간다 — 고른 것이 오답노트 표시다.
 * 끝 화면은 이번에 오답노트에 넣은 문제를 답·해설과 함께 펼쳐 둔다.
 * 틀리면 서버가 먼저 high(모르겠음)를 붙이고, 사람이 고른 값이 그 뒤에 덮는다.
 */
export function JokboPage() {
  const { eventId = "" } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<JokboResponse | null>(null);
  const [error, setError] = useState("");
  const [queue, setQueue] = useState<JokboItem[] | null>(null);
  const [round, setRound] = useState(0);
  const [bands, setBands] = useState<Record<string, JokboBand | null>>({});
  const bandsRef = useRef(bands);
  bandsRef.current = bands;
  // 채점 기록(틀리면 서버가 high를 붙인다)이 끝난 뒤에 표시를 쓴다. 순서가 뒤집히면 고른 표시가 high로 덮인다.
  const pending = useRef<Record<string, Promise<unknown>>>({});

  useEffect(() => {
    let alive = true;
    api<{ marks: JokboMark[] }>(`/api/jokbo/marks?eventId=${encodeURIComponent(eventId)}`)
      .then(got => { if (alive) setBands(prev => ({ ...Object.fromEntries(got.marks.map(m => [m.itemId, m.band])), ...prev })); })
      .catch(() => { /* 표시를 못 읽어도 풀 수는 있다 */ });
    return () => { alive = false; };
  }, [eventId]);

  const answered = useCallback((itemId: string, verdict: Verdict) => {
    if (verdict === "wrong") setBands(prev => ({ ...prev, [itemId]: "high" }));
    pending.current[itemId] = postAnswer(eventId, itemId, verdict).catch(() => { /* 기록 실패는 풀이를 막지 않는다 */ });
  }, [eventId]);

  const rate = useCallback((itemId: string, band: Shown) => {
    const before = bandsRef.current[itemId] ?? null;
    if (before === band) return; // 틀려서 서버가 이미 high, 또는 원래 표시 그대로
    setBands(prev => ({ ...prev, [itemId]: band }));
    const after = pending.current[itemId] ?? Promise.resolve();
    void after.then(() => putBand(eventId, itemId, band)).catch(() => { /* 다음 불러오기에서 서버 값으로 돌아간다 */ });
  }, [eventId]);

  useEffect(() => {
    let alive = true;
    api<JokboResponse>(`/api/jokbo/events/${encodeURIComponent(eventId)}`)
      .then(got => { if (alive) setData(got); })
      .catch((cause: unknown) => {
        if (alive) setError(cause instanceof ApiError && cause.status === 404 ? "이 강의의 족보가 아직 없습니다." : (cause as Error).message);
      });
    return () => { alive = false; };
  }, [eventId]);
  // 플로팅 노트의 「＋강의명」(2026-11-14 사용자: 족보 풀 때도 복습 퀴즈처럼). 이름은 머리줄과 같게.
  useNoteLecture(data ? lectureTitle(data.doc) : null);

  const back = () => (window.history.length > 1 ? navigate(-1) : navigate("/"));
  const start = (items: JokboItem[]) => { setQueue(items); setRound(r => r + 1); };

  if (error) return <main className="main-quiz-learning jokbo-learning"><p className="notice is-error">{error}</p></main>;
  if (!data) return <main className="main-quiz-learning jokbo-learning"><p className="event-panel-loading">불러오는 중…</p></main>;
  return (
    <main className={`main-quiz-learning jokbo-learning${queue ? "" : " is-start"}`}>
      {queue
        ? <JokboSolve key={round} doc={data.doc} items={queue} bands={bands}
            onExit={() => setQueue(null)} onLeave={back} onRetry={start} onAnswered={answered} onRate={rate} />
        : <JokboStart data={data} onBack={back} onStart={start} />}
    </main>
  );
}

/** 시간표 제목 앞의 분야 머리(「미생물학) 」)를 뗀다 — 강의 패널 제목과 같게. */
export function lectureTitle(doc: JokboDoc): string {
  return doc.lecture.title.replace(/^[^)\s]{1,8}\)\s*/, "");
}

// ─────────────────────────────────────────────── 진입

const STORE = "jokbo-scope:";

function loadChoice(doc: JokboDoc): { scope: JokboScope; years: string[] | null } {
  try {
    const raw = localStorage.getItem(STORE + doc.lecture.eventId);
    if (raw) {
      const got = JSON.parse(raw) as { scope?: JokboScope; years?: string[] };
      if (got.scope === "same" || got.scope === "more") return { scope: got.scope, years: Array.isArray(got.years) ? got.years : null };
    }
  } catch { /* 저장소가 막혀 있으면 기본값 */ }
  return { scope: defaultScope(doc), years: null };
}

function JokboStart({ data, onBack, onStart }: { data: JokboResponse; onBack: () => void; onStart: (items: JokboItem[]) => void }) {
  const doc = data.doc;
  const others = useMemo(() => otherYears(doc), [doc]);
  const sameCount = sameItemIds(doc).length;
  const initial = useMemo(() => loadChoice(doc), [doc]);
  const [scope, setScope] = useState<JokboScope>(sameCount ? initial.scope : "more");
  const [years, setYears] = useState<Set<string>>(() => {
    const known = new Set(others.map(y => y.key));
    const saved = initial.years?.filter(k => known.has(k));
    return new Set(saved && saved.length ? saved : others.map(y => y.key));
  });
  const items = pickItems(doc, scope, years);
  const allOn = others.length > 0 && others.every(y => years.has(y.key));

  useEffect(() => {
    try { localStorage.setItem(STORE + doc.lecture.eventId, JSON.stringify({ scope, years: [...years] })); } catch { /* 무시 */ }
  }, [doc.lecture.eventId, scope, years]);

  function toggle(key: string) {
    setYears(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  const otherCount = others.reduce((n, y) => n + y.itemIds.length, 0);
  return (
    <section className="mq-start jokbo-start">
      <header className="page-head mq-head">
        <div>
          <p className="mq-kicker">
            <button type="button" className="quiz-back" onClick={onBack}>
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10 3 5 8l5 5" /></svg>뒤로
            </button>
            <span className="mq-badge jokbo-badge">족보</span>
            {data.audience === "admin" ? <span className="jokbo-admin-tag">관리자만</span> : null}
          </p>
          <h1>{lectureTitle(doc)}</h1>
          {doc.lecture.currentProfessors.length ? <p className="jokbo-prof">{doc.lecture.currentProfessors.join(", ")}</p> : null}
        </div>
      </header>

      <div className="mq-stats">
        <div><span>전체</span><b>{doc.items.length}</b></div>
        <div className="is-recalled"><span>같은 교수</span><b>{sameCount}</b></div>
        <div><span>다른 교수</span><b>{otherCount}</b></div>
      </div>

      <section className="mq-today jokbo-scope" aria-label="범위">
        <div className="mq-today-text">
          <div className="mq-focus jokbo-scope-main" role="radiogroup" aria-label="교수">
            <button type="button" role="radio" aria-checked={scope === "same"} aria-pressed={scope === "same"}
              disabled={!sameCount} className={sameCount ? undefined : "is-empty"} onClick={() => setScope("same")}>
              {scope === "same" && <Icon.check />}같은 교수만<b>{sameCount}</b>
            </button>
            <button type="button" role="radio" aria-checked={scope === "more"} aria-pressed={scope === "more"}
              disabled={!otherCount} className={otherCount ? undefined : "is-empty"} onClick={() => setScope("more")}>
              {scope === "more" && <Icon.check />}다른 교수까지<b>{sameCount + otherCount}</b>
            </button>
          </div>
          {scope === "more" && others.length ? (
            <div className="mq-focus jokbo-years" role="group" aria-label="다른 교수 연도">
              <button type="button" aria-pressed={allOn}
                onClick={() => setYears(allOn ? new Set() : new Set(others.map(y => y.key)))}>
                {allOn && <Icon.check />}전체<b>{otherCount}</b>
              </button>
              {others.map(y => (
                <button key={y.key} type="button" aria-pressed={years.has(y.key)} onClick={() => toggle(y.key)}>
                  {years.has(y.key) && <Icon.check />}{y.label}<b>{y.itemIds.length}</b>
                </button>
              ))}
            </div>
          ) : null}
        </div>
        <button className="mq-start-button" disabled={!items.length} onClick={() => onStart(items)}>
          <Icon.play />시작<span className="mq-card-count" aria-label={`문제 ${items.length}개`}>{items.length}</span>
        </button>
      </section>
    </section>
  );
}

// ─────────────────────────────────────────────── 풀이

type Result = { item: JokboItem; verdict: Verdict; picked: number[]; band?: Shown };

const BACK_ICON = (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10 3 5 8l5 5" /></svg>
);

function JokboSolve({ doc, items, bands, onExit, onLeave, onRetry, onAnswered, onRate }: {
  doc: JokboDoc; items: JokboItem[];
  bands: Record<string, JokboBand | null>;
  onExit: () => void; onLeave: () => void; onRetry: (items: JokboItem[]) => void;
  onAnswered: (itemId: string, verdict: Verdict) => void;
  onRate: (itemId: string, band: Shown) => void;
}) {
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<number[]>([]);
  const [shown, setShown] = useState(false);
  const [results, setResults] = useState<Result[]>([]);
  const item = items[index] as JokboItem | undefined;
  const verdict = shown ? results[results.length - 1]?.verdict : undefined;
  // 독의 기본값(Enter·Space): 틀렸으면 모르겠음, 그 밖은 괜찮음.
  const suggested: Shown = verdict === "wrong" ? "high" : null;

  const reveal = useCallback((choice: number[]) => {
    if (!item || shown) return;
    const v: Verdict = choice.length ? grade(item, choice) : (item.answerStatus === "missing" ? "ungraded" : "wrong");
    setPicked(choice);
    setShown(true);
    setResults(prev => [...prev, { item, verdict: v, picked: choice }]);
    onAnswered(item.id, v);
  }, [item, shown, onAnswered]);

  const rate = useCallback((band: Shown) => {
    if (!item || !shown) return;
    onRate(item.id, band);
    setResults(prev => prev.map((r, i) => (i === prev.length - 1 ? { ...r, band } : r)));
    setIndex(i => i + 1);
    setPicked([]);
    setShown(false);
    window.scrollTo({ top: 0 });
  }, [item, shown, onRate]);

  const pick = useCallback((n: number) => {
    if (!item || shown) return;
    if (needed(item) === 1) { reveal([n]); return; }
    setPicked(prev => (prev.includes(n) ? prev.filter(x => x !== n) : [...prev, n]));
  }, [item, shown, reveal]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.repeat || event.isComposing || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.target instanceof HTMLElement
        && event.target.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])")) return;
      if (!item) return;
      const n = Number(event.key);
      const enter = event.key === "Enter" || event.key === " ";
      if (!shown) {
        if (Number.isInteger(n) && n >= 1 && n <= item.choices.length) { event.preventDefault(); pick(n); }
        else if (enter) { event.preventDefault(); reveal(picked); }
        return;
      }
      if (Number.isInteger(n) && n >= 1 && n <= RATINGS.length) { event.preventDefault(); rate(RATINGS[n - 1].key); }
      else if (enter) { event.preventDefault(); rate(suggested); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [item, shown, picked, pick, reveal, rate, suggested]);

  const head = (
    <header className="pq-head">
      <p className="pq-kicker">
        <button type="button" className="quiz-back" onClick={onExit}>{BACK_ICON}뒤로</button>
        <span className="pq-badge jokbo-badge">족보</span>
        <span className="pq-title">{lectureTitle(doc)}</span>
      </p>
    </header>
  );

  if (!item) return <JokboDone head={head} items={items} results={results} bands={bands} onLeave={onLeave} onRetry={onRetry} />;

  const who = professorsOf(doc, item.id);
  const asked = yearsOf(item);
  // 반복 표시: 합친 사본의 연도가 정본이고, 없으면 원천이 적어 둔 반복 연도(다른 강의로 간 사본 포함).
  const repeat = asked.length > 1 ? asked : item.repeatYears?.length ? item.repeatYears : [];
  const changed = new Set(changedChoices(item, items[index - 1]));
  const need = needed(item);
  return (
    <section className="prequiz-learning quiz jokbo-solve">
      {head}
      <div className="pq-progress" aria-live="polite">
        <h2 className="pq-count">족보 {index + 1} / {items.length}</h2>
        <span className="pq-track jokbo-track" aria-hidden="true"><i style={{ width: `${(index / items.length) * 100}%` }} /></span>
      </div>

      <div className="pq-card jokbo-card">
        <div className="jokbo-meta">
          <span className={`jokbo-who is-${who.kind}`}>{item.yearLabel} {who.professors.join(", ") || "교수 미상"}</span>
          <span className="jokbo-num">{item.number}번</span>
          {repeat.length > 1 ? <span className="jokbo-repeat">출제 {repeat.join("·")}</span> : null}
          {changed.size ? <span className="jokbo-variant">변형 · 바뀐 선지 {changed.size}</span> : null}
        </div>
        <JokboBody item={item} picked={picked} revealed={shown} verdict={verdict} changed={changed} onPick={pick} eagerImages />
        {!shown && need > 1 ? <p className="bank-note jokbo-need">{need}개</p> : null}
      </div>

      <div className="quiz-bar pq-dock jokbo-dock" aria-label={shown ? "오답노트" : "답"}>
        {shown ? RATINGS.map((r, i) => {
          const isDefault = r.key === suggested;
          return (
            <button key={r.tone} className={`quiz-grade jokbo-rate is-${r.tone}${isDefault ? " is-default" : ""}`}
              onClick={() => rate(r.key)} aria-keyshortcuts={isDefault ? `${i + 1} Enter Space` : String(i + 1)}>
              <span className="quiz-grade-name">{r.label} <kbd>{isDefault ? `${i + 1} / Enter` : i + 1}</kbd></span>
            </button>
          );
        }) : (
          <button className="quiz-submit jokbo-reveal" onClick={() => reveal(picked)}
            disabled={need > 1 && picked.length !== need && picked.length !== 0}
            aria-keyshortcuts="Enter Space">{picked.length ? "확인" : "답 보기"} <kbd>Enter</kbd></button>
        )}
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────── 끝

/** 예습 퀴즈 완료 화면처럼: 요약 상자, 그 아래 이번에 오답노트에 넣은 문제를 답·해설과 함께 펼친다. */
function JokboDone({ head, items, results, bands, onLeave, onRetry }: {
  head: ReactNode; items: JokboItem[]; results: Result[];
  bands: Record<string, JokboBand | null>;
  onLeave: () => void; onRetry: (items: JokboItem[]) => void;
}) {
  const kept = results.filter(r => r.band);
  const right = results.filter(r => r.verdict === "correct").length;
  const unknown = results.filter(r => r.band === "high").length;
  const caution = results.filter(r => r.band === "mid").length;
  return (
    <section className="prequiz-learning pq-done jokbo-done">
      {head}
      <div className="pq-today jokbo-today">
        <div className="pq-today-text">
          <h2>족보 완료</h2>
          <p><b>{results.length}</b>문항 · 맞힘 <b>{right}</b>
            {unknown ? <> · 모르겠음 <b className="jokbo-count-unknown">{unknown}</b></> : null}
            {caution ? <> · 주의 <b className="jokbo-count-caution">{caution}</b></> : null}</p>
        </div>
        <div className="pq-actions">
          <button className="pill-button" onClick={() => onRetry(items)}>다시 풀기</button>
          <button className="pq-start-button jokbo-finish" onClick={onLeave}>족보 마치기</button>
        </div>
      </div>

      {kept.length ? (
        <section className="prequiz-difficult jokbo-kept">
          <header className="prequiz-difficult-head">
            <h3>오답노트에 넣은 문제 <b>{kept.length}</b></h3>
            <span className="jokbo-kept-tools">
              <Link className="pill-button" to="/wrong-notes">오답노트</Link>
              <button className="pill-button" onClick={() => onRetry(kept.map(r => r.item))}>이 문제만 다시 풀기</button>
            </span>
          </header>
          <ol className="jokbo-kept-list">
            {kept.map((r, i) => {
              const now = r.item.id in bands ? shownBand(bands[r.item.id]) : (r.band ?? null);
              const label = RATINGS.find(x => x.key === now) ?? RATINGS[2];
              return (
                <li key={r.item.id} className={`jokbo-kept-card is-${label.tone}`}>
                  <div className="jokbo-meta">
                    <span className="jokbo-kept-index">{i + 1}</span>
                    <span className={`jokbo-rating-tag is-${label.tone}`}>{label.label}</span>
                    <span className="jokbo-who">{r.item.yearLabel}</span>
                    <span className="jokbo-num">{r.item.number}번</span>
                  </div>
                  <JokboBody item={r.item} picked={r.picked} revealed verdict={r.verdict} />
                </li>
              );
            })}
          </ol>
        </section>
      ) : null}
    </section>
  );
}
