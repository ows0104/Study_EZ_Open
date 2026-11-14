import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { jokboHref } from "../links";
import type { JokboBand, JokboItem, JokboNoteEntry, JokboNotes } from "../types/jokbo";
import { BANDS, BandButtons, postAnswer, putBand } from "./marks";
import { grade, needed, type Verdict } from "./selection";
import "../bank/main-quiz.css";
import "./jokbo.css";

/**
 * 족보 오답노트(2026-11-14 사용자 지시). amgi 족보 오답노트처럼 강의를 가리지 않고 한 화면에 모은다.
 *
 * 풀기     답을 가린다. 선지를 고르면 채점하고(틀리면 다시 「상 틀림」), 「답 보기」로 그냥 열 수도 있다.
 * 정답 보기 정답·선지별 해설·해설이 처음부터 펴져 있다.
 *
 * 목록은 들어올 때 한 번 세운다. 표시를 떼거나 바꿔도 줄이 그 자리에 남는다 — 잘못 누른 것을
 * 되돌릴 수 있고 훑던 자리를 잃지 않는다. 거르기도 들어올 때의 표시로 한다.
 */
type View = "solve" | "note";
const VIEW_KEY = "jokbo-wrong-view";

function loadView(): View {
  try { return localStorage.getItem(VIEW_KEY) === "note" ? "note" : "solve"; } catch { return "solve"; }
}

function lectureLabel(e: JokboNoteEntry): string {
  const title = e.lecture.title.replace(/^[^)\s]{1,8}\)\s*/, "");
  return /^\d+$/.test(e.lecture.number) ? `${e.lecture.number}. ${title}` : title;
}

export function WrongNotePage() {
  const [data, setData] = useState<JokboNotes | null>(null);
  const [error, setError] = useState("");
  const [bands, setBands] = useState<Record<string, JokboBand | null>>({});
  const [view, setView] = useState<View>(loadView);
  const [on, setOn] = useState<Record<JokboBand, boolean>>({ high: true, mid: true, low: true });
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let alive = true;
    api<JokboNotes>("/api/jokbo/wrong-notes")
      .then(got => {
        if (!alive) return;
        setData(got);
        setBands(Object.fromEntries(got.items.map(e => [e.item.id, e.mark.band])));
      })
      .catch((cause: unknown) => { if (alive) setError((cause as Error).message); });
    return () => { alive = false; };
  }, []);

  const count = useMemo(() => {
    const c: Record<JokboBand, number> = { high: 0, mid: 0, low: 0 };
    for (const e of data?.items ?? []) if (e.mark.band) c[e.mark.band] += 1;
    return c;
  }, [data]);

  function switchView(next: View) {
    setView(next);
    if (next === "solve") setShowAll(false);
    try { localStorage.setItem(VIEW_KEY, next); } catch { /* 이번 화면만 바뀐다 */ }
  }

  function setBand(e: JokboNoteEntry, band: JokboBand | null) {
    setBands(prev => ({ ...prev, [e.item.id]: band }));
    putBand(e.lecture.eventId, e.item.id, band)
      .then(m => setBands(prev => ({ ...prev, [e.item.id]: m.band })))
      .catch(() => { /* 다음에 들어오면 서버 값 */ });
  }

  function answered(e: JokboNoteEntry, verdict: Verdict) {
    if (verdict === "wrong") setBands(prev => ({ ...prev, [e.item.id]: "high" }));
    postAnswer(e.lecture.eventId, e.item.id, verdict)
      .then(m => setBands(prev => ({ ...prev, [e.item.id]: m.band })))
      .catch(() => { /* 기록 실패는 화면을 막지 않는다 */ });
  }

  if (error) return <main className="main-quiz-learning jokbo-learning"><p className="notice is-error">{error}</p></main>;
  if (!data) return <main className="main-quiz-learning jokbo-learning"><p className="event-panel-loading">불러오는 중…</p></main>;

  const note = view === "note";
  const shown = data.items.filter(e => e.mark.band && on[e.mark.band]);
  return (
    <main className="main-quiz-learning jokbo-learning jokbo-notes">
      <header className="page-head mq-head">
        <div>
          <p className="mq-kicker"><span className="mq-badge jokbo-badge">족보</span></p>
          <h1>오답노트 <span className="jokbo-notes-count">{data.items.length}</span></h1>
        </div>
      </header>

      <div className="jokbo-notes-bar">
        <div className="mq-focus" role="radiogroup" aria-label="보기">
          <button type="button" role="radio" aria-checked={!note} aria-pressed={!note} onClick={() => switchView("solve")}>풀기</button>
          <button type="button" role="radio" aria-checked={note} aria-pressed={note} onClick={() => switchView("note")}>정답 보기</button>
        </div>
        <div className="mq-focus" role="group" aria-label="표시">
          {BANDS.map(b => (
            <button key={b.key} type="button" aria-pressed={on[b.key]} className={count[b.key] ? undefined : "is-empty"}
              onClick={() => setOn(prev => ({ ...prev, [b.key]: !prev[b.key] }))}>
              {b.label} {b.word}<b>{count[b.key]}</b>
            </button>
          ))}
        </div>
        {!note && shown.length ? (
          <button type="button" className="pill-button" aria-pressed={showAll} onClick={() => setShowAll(v => !v)}>
            {showAll ? "답 가리기" : "답 전부 보기"}
          </button>
        ) : null}
      </div>

      {data.missing ? <p className="jokbo-notes-missing">볼 수 없는 문제 {data.missing}</p> : null}

      {shown.length ? (
        <ol className="jokbo-notes-list">
          {shown.map((e, i) => (
            <NoteCard key={e.item.id} entry={e} index={i + 1} open={note || showAll}
              band={bands[e.item.id] ?? null} onBand={band => setBand(e, band)} onAnswered={v => answered(e, v)} />
          ))}
        </ol>
      ) : (
        (data.items.length ? null : <p className="jokbo-notes-empty">비어 있음</p>)
      )}
    </main>
  );
}

function NoteCard({ entry, index, open, band, onBand, onAnswered }: {
  entry: JokboNoteEntry; index: number; open: boolean;
  band: JokboBand | null;
  onBand: (band: JokboBand | null) => void;
  onAnswered: (verdict: Verdict) => void;
}) {
  const item: JokboItem = entry.item;
  const [picked, setPicked] = useState<number[]>([]);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const revealed = open || verdict !== null;
  const need = needed(item);
  const entered = BANDS.find(b => b.key === entry.mark.band);
  const x = item.explanation;
  const years = item.years?.length ? item.years : [item.yearLabel];

  function check(choice: number[]) {
    if (verdict !== null) return;
    const v: Verdict = choice.length ? grade(item, choice) : "ungraded";
    setPicked(choice);
    setVerdict(v);
    if (choice.length) onAnswered(v);
  }

  function pick(n: number) {
    if (revealed) return;
    if (need === 1) { check([n]); return; }
    setPicked(prev => (prev.includes(n) ? prev.filter(c => c !== n) : [...prev, n]));
  }

  return (
    <li className={`quiz-card bank-card jokbo-card jokbo-note${band ? ` is-${band}` : " is-cleared"}`}>
      <div className="jokbo-note-meta">
        <span className="jokbo-note-index">{index}</span>
        {entered ? <span className={`jokbo-band-tag is-${entered.key}`}>{entered.label} {entered.word}</span> : null}
        {!band ? <span className="jokbo-note-cleared">뗌</span> : band !== entry.mark.band ? (
          <span className="jokbo-note-now">지금 {BANDS.find(b => b.key === band)?.label}</span>
        ) : null}
        <Link className="jokbo-note-lecture" to={jokboHref(entry.lecture.eventId)}>{lectureLabel(entry)}</Link>
        <span className={`jokbo-who is-${entry.kind}`}>{years.join("·")} {entry.professors.join(", ") || "교수 미상"}</span>
        <span className="jokbo-note-num">{item.number}번</span>
        {entry.mark.wrongCount ? <span className="jokbo-note-wrong">틀림 {entry.mark.wrongCount}</span> : null}
      </div>

      {item.sharedPrompt ? <p className="jokbo-shared">{item.sharedPrompt}</p> : null}
      <p className="jokbo-stem">{item.stem}</p>
      {item.figures?.length ? (
        <div className="jokbo-figures">
          {item.figures.map(f => (f.url ? <img key={f.file} src={f.url} alt="" width={f.w} height={f.h} loading="lazy" /> : null))}
        </div>
      ) : null}

      <ul className="bank-options jokbo-options">
        {item.choices.map((choice, i) => {
          const n = i + 1;
          const selected = picked.includes(n);
          const key = item.answerStatus === "all-correct" || item.answers.includes(n);
          const cls = !revealed ? (selected ? " is-picked" : "")
            : item.answerStatus === "missing" ? (selected ? " is-picked" : "")
            : key ? (selected ? " is-correct" : " is-missed") : selected ? " is-wrong" : "";
          const choiceNote = revealed ? x?.choiceNotes?.[i] : undefined;
          return (
            <li key={n}>
              <button type="button" className={`bank-option${cls}`} disabled={revealed} aria-pressed={selected} onClick={() => pick(n)}>
                <b>{n}</b> {choice}
              </button>
              {choiceNote ? <p className="jokbo-choice-note">{choiceNote}</p> : null}
            </li>
          );
        })}
      </ul>

      {revealed ? (
        <div className="jokbo-answer">
          <p className={`jokbo-verdict is-${verdict ?? "ungraded"}`}>
            {verdict === "correct" ? "맞음" : verdict === "wrong" ? "틀림" : null}
            <span>
              {item.answerStatus === "all-correct" ? "전원 정답"
                : item.answerStatus === "missing"
                  ? `답안지에 답 없음${x?.proposedAnswers?.length ? ` · 추정 ${x.proposedAnswers.join(", ")}` : ""}`
                  : `정답 ${item.answers.join(item.answerMode === "all_of" ? " + " : " 또는 ")}`}
            </span>
          </p>
          {item.keyConflict && item.mergedFrom ? (
            <p className="jokbo-caution">해마다 답안지 답이 다름: {item.yearLabel} {item.answers.join(",")}
              {item.mergedFrom.map(m => ` · ${m.yearLabel} ${m.answers.join(",") || "–"}`).join("")}</p>
          ) : null}
          {x?.caution ? <p className="jokbo-caution">{x.caution}</p> : null}
          {x ? <p className="jokbo-explain">{x.text}</p> : null}
          {item.correctionNote ? <p className="jokbo-correction">교정: {item.correctionNote}</p> : null}
        </div>
      ) : (
        <div className="jokbo-note-actions">
          {need > 1 ? (
            <button type="button" className="quiz-submit" disabled={picked.length !== need} onClick={() => check(picked)}>확인 · {need}개</button>
          ) : null}
          <button type="button" className="pill-button" onClick={() => check([])}>답 보기</button>
        </div>
      )}

      <BandButtons band={band} onChange={onBand} />
    </li>
  );
}
