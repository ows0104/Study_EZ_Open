import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { Icon } from "../shell/icons";
import type { JokboBand, JokboDoc, JokboItem, JokboMark, JokboResponse } from "../types/jokbo";
import { BandButtons, postAnswer, putBand } from "./marks";
import {
  changedChoices, defaultScope, grade, needed, otherYears, pickItems, professorsOf, sameItemIds, yearsOf,
  type JokboScope, type Verdict,
} from "./selection";
import "../bank/main-quiz.css";
import "./jokbo.css";

/**
 * 강의별 족보 퀴즈(2026-11-13 사용자 지시).
 *
 * 진입 화면에서 범위(같은 교수만 / 다른 교수까지 + 연도)를 고르고, 복습 퀴즈처럼
 * **한 문제씩** 푼다. 고르면 바로 정답·선지별 해설이 나온다.
 *
 * 풀면 결과를 서버에 남긴다(2026-11-14 오답노트). 틀리면 오답노트에 「상 틀림」으로 담기고,
 * 답 아래 상·중·하로 직접 담거나 뗀다. 복습 퀴즈식 간격 채점은 아직 없다(사용자 결정 대기).
 */
export function JokboPage() {
  const { eventId = "" } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<JokboResponse | null>(null);
  const [error, setError] = useState("");
  const [queue, setQueue] = useState<JokboItem[] | null>(null);
  const [bands, setBands] = useState<Record<string, JokboBand | null>>({});

  useEffect(() => {
    let alive = true;
    api<{ marks: JokboMark[] }>(`/api/jokbo/marks?eventId=${encodeURIComponent(eventId)}`)
      .then(got => { if (alive) setBands(Object.fromEntries(got.marks.map(m => [m.itemId, m.band]))); })
      .catch(() => { /* 표시를 못 읽어도 풀 수는 있다 */ });
    return () => { alive = false; };
  }, [eventId]);

  const saved = useCallback((mark: JokboMark) => setBands(prev => ({ ...prev, [mark.itemId]: mark.band })), []);
  const answered = useCallback((itemId: string, verdict: Verdict) => {
    if (verdict === "wrong") setBands(prev => ({ ...prev, [itemId]: "high" }));
    postAnswer(eventId, itemId, verdict).then(saved).catch(() => { /* 기록 실패는 풀이를 막지 않는다 */ });
  }, [eventId, saved]);
  const changeBand = useCallback((itemId: string, band: JokboBand | null) => {
    setBands(prev => ({ ...prev, [itemId]: band }));
    putBand(eventId, itemId, band).then(saved).catch(() => { /* 다음 불러오기에서 서버 값으로 돌아간다 */ });
  }, [eventId, saved]);

  useEffect(() => {
    let alive = true;
    api<JokboResponse>(`/api/jokbo/events/${encodeURIComponent(eventId)}`)
      .then(got => { if (alive) setData(got); })
      .catch((cause: unknown) => {
        if (alive) setError(cause instanceof ApiError && cause.status === 404 ? "이 강의의 족보가 아직 없습니다." : (cause as Error).message);
      });
    return () => { alive = false; };
  }, [eventId]);

  const back = () => (window.history.length > 1 ? navigate(-1) : navigate("/"));

  if (error) return <main className="main-quiz-learning jokbo-learning"><p className="notice is-error">{error}</p></main>;
  if (!data) return <main className="main-quiz-learning jokbo-learning"><p className="event-panel-loading">불러오는 중…</p></main>;
  return (
    <main className={`main-quiz-learning jokbo-learning${queue ? "" : " is-start"}`}>
      {queue
        ? <JokboSolve doc={data.doc} items={queue} onExit={() => setQueue(null)} onRetry={setQueue}
            bands={bands} onAnswered={answered} onBand={changeBand} />
        : <JokboStart data={data} onBack={back} onStart={setQueue} />}
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

type Result = { id: string; verdict: Verdict };

function JokboSolve({ doc, items, onExit, onRetry, bands, onAnswered, onBand }: {
  doc: JokboDoc; items: JokboItem[]; onExit: () => void; onRetry: (items: JokboItem[]) => void;
  bands: Record<string, JokboBand | null>;
  onAnswered: (itemId: string, verdict: Verdict) => void;
  onBand: (itemId: string, band: JokboBand | null) => void;
}) {
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<number[]>([]);
  const [shown, setShown] = useState(false);
  const [results, setResults] = useState<Result[]>([]);
  const item = items[index] as JokboItem | undefined;

  const reveal = useCallback((choice: number[]) => {
    if (!item || shown) return;
    const verdict: Verdict = choice.length ? grade(item, choice) : (item.answerStatus === "missing" ? "ungraded" : "wrong");
    setPicked(choice);
    setShown(true);
    setResults(prev => [...prev, { id: item.id, verdict }]);
    onAnswered(item.id, verdict);
  }, [item, shown, onAnswered]);

  const next = useCallback(() => {
    setIndex(i => i + 1);
    setPicked([]);
    setShown(false);
    window.scrollTo({ top: 0 });
  }, []);

  const pick = useCallback((n: number) => {
    if (!item || shown) return;
    if (needed(item) === 1) { reveal([n]); return; }
    setPicked(prev => {
      const has = prev.includes(n);
      const out = has ? prev.filter(x => x !== n) : [...prev, n];
      return out;
    });
  }, [item, shown, reveal]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.target instanceof HTMLElement && /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
      if (!item) return;
      const n = Number(event.key);
      if (!shown && Number.isInteger(n) && n >= 1 && n <= item.choices.length) { event.preventDefault(); pick(n); return; }
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        if (shown) next();
        else reveal(picked);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [item, shown, picked, pick, reveal, next]);

  if (!item) {
    const wrongIds = new Set(results.filter(r => r.verdict === "wrong").map(r => r.id));
    const count = (v: Verdict) => results.filter(r => r.verdict === v).length;
    return (
      <section className="jokbo-done">
        <h2>{lectureTitle(doc)}</h2>
        <div className="mq-stats">
          <div className="is-recalled"><span>맞힘</span><b>{count("correct")}</b></div>
          <div className="is-wrong"><span>틀림</span><b>{count("wrong")}</b></div>
          {count("ungraded") ? <div><span>답 없음</span><b>{count("ungraded")}</b></div> : null}
        </div>
        <div className="jokbo-done-actions">
          {wrongIds.size ? (
            <button className="mq-start-button" onClick={() => onRetry(items.filter(it => wrongIds.has(it.id)))}>
              <Icon.play />틀린 문제 다시<span className="mq-card-count">{wrongIds.size}</span>
            </button>
          ) : null}
          <button className="pill-button" onClick={onExit}>범위 다시 고르기</button>
        </div>
      </section>
    );
  }

  const who = professorsOf(doc, item.id);
  const asked = yearsOf(item);
  // 반복 표시: 합친 사본의 연도가 정본이고, 없으면 원천이 적어 둔 반복 연도(다른 강의로 간 사본 포함).
  const repeat = asked.length > 1 ? asked : item.repeatYears?.length ? item.repeatYears : [];
  const changed = new Set(changedChoices(item, items[index - 1]));
  const verdict = shown ? results[results.length - 1]?.verdict : undefined;
  const need = needed(item);
  const x = item.explanation;
  return (
    <section className="jokbo-solve">
      <div className="quiz-top jokbo-top">
        <button type="button" className="quiz-back" onClick={onExit}>
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10 3 5 8l5 5" /></svg>범위
        </button>
        <span className="jokbo-progress">{index + 1} / {items.length}</span>
        <span className="jokbo-meta">
          <span className={`jokbo-who is-${who.kind}`}>{item.yearLabel} {who.professors.join(", ") || "교수 미상"}</span>
          {repeat.length > 1 ? <span className="jokbo-repeat">출제 {repeat.join("·")}</span> : null}
          {changed.size ? <span className="jokbo-variant">변형 · 바뀐 선지 {changed.size}</span> : null}
        </span>
      </div>

      <div className="quiz-card bank-card mq-card jokbo-card">
        {item.sharedPrompt ? <p className="jokbo-shared">{item.sharedPrompt}</p> : null}
        <p className="jokbo-stem">{item.stem}</p>
        {item.figures?.length ? (
          <div className="jokbo-figures">
            {item.figures.map(f => f.url ? <img key={f.file} src={f.url} alt="" width={f.w} height={f.h} loading="eager" /> : null)}
          </div>
        ) : null}
        <ul className="bank-options jokbo-options">
          {item.choices.map((choice, i) => {
            const n = i + 1;
            const selected = picked.includes(n);
            const key = item.answerStatus === "all-correct" || item.answers.includes(n);
            const cls = !shown ? (selected ? " is-picked" : "")
              : item.answerStatus === "missing" ? (selected ? " is-picked" : "")
              : key ? (selected ? " is-correct" : " is-missed") : selected ? " is-wrong" : "";
            const note = shown ? x?.choiceNotes?.[i] : undefined;
            return (
              <li key={n}>
                <button type="button" className={`bank-option${cls}${changed.has(i) ? " is-changed" : ""}`} disabled={shown} aria-pressed={selected}
                  aria-keyshortcuts={n <= 9 ? String(n) : undefined} onClick={() => pick(n)}>
                  <b>{n}</b> {choice}
                </button>
                {note ? <p className="jokbo-choice-note">{note}</p> : null}
              </li>
            );
          })}
        </ul>
        {!shown && need > 1 ? <p className="bank-note">{need}개</p> : null}

        {shown ? (
          <div className="jokbo-answer" role="status">
            <p className={`jokbo-verdict is-${verdict}`}>
              {verdict === "correct" ? "맞음" : verdict === "wrong" ? "틀림" : "답안지에 답 없음"}
              <span>
                {item.answerStatus === "all-correct" ? "전원 정답"
                  : item.answerStatus === "missing"
                    ? (x?.proposedAnswers?.length ? `추정 ${x.proposedAnswers.join(", ")}` : "")
                    : `정답 ${item.answers.join(item.answerMode === "all_of" ? " + " : " 또는 ")}`}
              </span>
            </p>
            {item.keyConflict && item.mergedFrom ? (
              <p className="jokbo-caution">해마다 답안지 답이 다름: {item.yearLabel} {item.answers.join(",")}
                {item.mergedFrom.map(m => ` · ${m.yearLabel} ${m.answers.join(",") || "–"}`).join("")}</p>
            ) : null}
            <BandButtons band={bands[item.id] ?? null} onChange={band => onBand(item.id, band)} />
            {x?.caution ? <p className="jokbo-caution">{x.caution}</p> : null}
            {x ? <p className="jokbo-explain">{x.text}</p> : null}
            {item.correctionNote ? <p className="jokbo-correction">교정: {item.correctionNote}</p> : null}
            {x ? (
              <p className="jokbo-basis">
                {x.basis.kind === "notes" ? `필기${x.basis.pages?.length ? ` p.${x.basis.pages.join(", ")}` : ""}` : "일반 지식"}
                {" · "}{[item, ...(item.mergedFrom ?? [])].map(c => `${c.yearLabel} ${c.number}번`).join(" · ")}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="quiz-bar bank-solve-bar">
        {shown ? (
          <button className="quiz-submit" onClick={next} aria-keyshortcuts="Enter Space">다음 <kbd>Enter</kbd></button>
        ) : (
          <button className="quiz-submit" onClick={() => reveal(picked)} disabled={need > 1 && picked.length !== need && picked.length !== 0}
            aria-keyshortcuts="Enter Space">{picked.length ? "확인" : "답 보기"} <kbd>Enter</kbd></button>
        )}
      </div>
    </section>
  );
}
