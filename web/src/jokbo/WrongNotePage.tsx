import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { jokboHref } from "../links";
import type { JokboBand, JokboNoteEntry, JokboNotes } from "../types/jokbo";
import { JokboBody } from "./JokboBody";
import { RATINGS, RatingButtons, postAnswer, putBand, shownBand, type Shown } from "./marks";
import { grade, needed, type Verdict } from "./selection";
import "../bank/main-quiz.css";
import "./jokbo.css";

/**
 * 족보 오답노트(2026-11-14 사용자 지시). 족보 퀴즈에서 모르겠음·주의로 넣은 문제를 모은다.
 *
 * 강의 칩으로 거르고, 목록은 강의별로 묶는다(2026-11-14 개편 「강의별로 분류」).
 * 카드는 답을 가린 채 시작한다. 선지를 고르면 채점하고(틀리면 다시 모르겠음), 「답 보기」로 그냥 열 수도 있다.
 * 맨 위 「전체 정답 보기」가 모든 카드를 한 번에 연다(예전 풀기/정답 보기 토글은 없앴다).
 *
 * 목록은 들어올 때 한 번 세운다. 괜찮음으로 빼거나 바꿔도 줄이 그 자리에 남는다 — 잘못 누른 것을
 * 되돌릴 수 있고 훑던 자리를 잃지 않는다. 거르기도 들어올 때의 표시로 한다. 예전 low는 주의로 센다.
 */
type Lecture = { eventId: string; label: string; date: string; count: number };

function lectureLabel(e: JokboNoteEntry): string {
  const title = e.lecture.title.replace(/^[^)\s]{1,8}\)\s*/, "");
  return /^\d+$/.test(e.lecture.number) ? `${e.lecture.number}. ${title}` : title;
}

const RANK: Record<string, number> = { high: 0, mid: 1 };

export function WrongNotePage() {
  const [data, setData] = useState<JokboNotes | null>(null);
  const [error, setError] = useState("");
  const [bands, setBands] = useState<Record<string, JokboBand | null>>({});
  const [lecture, setLecture] = useState<string>("all");
  const [on, setOn] = useState<{ high: boolean; mid: boolean }>({ high: true, mid: true });
  const [showAll, setShowAll] = useState(false);
  const pending = useRef<Record<string, Promise<unknown>>>({});

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

  // 들어올 때의 표시(예전 low는 주의)로 센다·거른다·늘어놓는다.
  const entries = useMemo(() => (data?.items ?? [])
    .map((e, order) => ({ e, band: shownBand(e.mark.band), order }))
    .filter((x): x is { e: JokboNoteEntry; band: "high" | "mid"; order: number } => x.band !== null), [data]);

  const lectures = useMemo(() => {
    const out = new Map<string, Lecture>();
    for (const { e } of entries) {
      const got = out.get(e.lecture.eventId);
      if (got) got.count += 1;
      else out.set(e.lecture.eventId, { eventId: e.lecture.eventId, label: lectureLabel(e), date: e.lecture.date, count: 1 });
    }
    return [...out.values()].sort((a, b) => a.date.localeCompare(b.date) || a.label.localeCompare(b.label, "ko"));
  }, [entries]);

  const inLecture = entries.filter(x => lecture === "all" || x.e.lecture.eventId === lecture);
  const count = { high: inLecture.filter(x => x.band === "high").length, mid: inLecture.filter(x => x.band === "mid").length };
  const shown = inLecture.filter(x => on[x.band]);
  const groups = lectures
    .map(l => ({ lecture: l, rows: shown.filter(x => x.e.lecture.eventId === l.eventId)
      .sort((a, b) => RANK[a.band] - RANK[b.band] || a.order - b.order) }))
    .filter(g => g.rows.length);

  function setBand(e: JokboNoteEntry, band: Shown) {
    setBands(prev => ({ ...prev, [e.item.id]: band }));
    const after = pending.current[e.item.id] ?? Promise.resolve();
    void after.then(() => putBand(e.lecture.eventId, e.item.id, band))
      .then(m => setBands(prev => ({ ...prev, [e.item.id]: m.band })))
      .catch(() => { /* 다음에 들어오면 서버 값 */ });
  }

  function answered(e: JokboNoteEntry, verdict: Verdict) {
    if (verdict === "wrong") setBands(prev => ({ ...prev, [e.item.id]: "high" }));
    pending.current[e.item.id] = postAnswer(e.lecture.eventId, e.item.id, verdict)
      .then(m => setBands(prev => ({ ...prev, [e.item.id]: m.band })))
      .catch(() => { /* 기록 실패는 화면을 막지 않는다 */ });
  }

  if (error) return <main className="main-quiz-learning jokbo-learning"><p className="notice is-error">{error}</p></main>;
  if (!data) return <main className="main-quiz-learning jokbo-learning"><p className="event-panel-loading">불러오는 중…</p></main>;

  let index = 0;
  return (
    <main className="main-quiz-learning jokbo-learning jokbo-notes">
      <header className="page-head mq-head">
        <div>
          <p className="mq-kicker"><span className="mq-badge jokbo-badge">족보</span></p>
          <h1>오답노트 <span className="jokbo-notes-count">{entries.length}</span></h1>
        </div>
      </header>

      {lectures.length ? (
        <div className="mq-focus jokbo-notes-lectures" role="radiogroup" aria-label="강의">
          <button type="button" role="radio" aria-checked={lecture === "all"} aria-pressed={lecture === "all"}
            onClick={() => setLecture("all")}>전체<b>{entries.length}</b></button>
          {lectures.map(l => (
            <button key={l.eventId} type="button" role="radio" aria-checked={lecture === l.eventId} aria-pressed={lecture === l.eventId}
              onClick={() => setLecture(l.eventId)}>{l.label}<b>{l.count}</b></button>
          ))}
        </div>
      ) : null}

      {entries.length ? (
        <div className="jokbo-notes-bar">
          <div className="mq-focus" role="group" aria-label="표시">
            {RATINGS.filter((r): r is typeof r & { key: "high" | "mid" } => r.key !== null).map(r => (
              <button key={r.tone} type="button" aria-pressed={on[r.key]} className={count[r.key] ? undefined : "is-empty"}
                onClick={() => setOn(prev => ({ ...prev, [r.key]: !prev[r.key] }))}>
                {r.label}<b>{count[r.key]}</b>
              </button>
            ))}
          </div>
          <button type="button" className="pill-button jokbo-show-all" aria-pressed={showAll} onClick={() => setShowAll(v => !v)}>
            {showAll ? "전체 정답 가리기" : "전체 정답 보기"}
          </button>
        </div>
      ) : null}

      {data.missing ? <p className="jokbo-notes-missing">볼 수 없는 문제 {data.missing}</p> : null}

      {groups.length ? groups.map(g => (
        <section key={g.lecture.eventId} className="jokbo-notes-group">
          <h2 className="jokbo-notes-group-head">
            <Link to={jokboHref(g.lecture.eventId)}>{g.lecture.label}</Link>
            <span>{g.rows.length}</span>
          </h2>
          <ol className="jokbo-notes-list">
            {g.rows.map(({ e, band }) => {
              index += 1;
              return (
                <NoteCard key={e.item.id} entry={e} entered={band} index={index} open={showAll}
                  band={bands[e.item.id] ?? null} onBand={next => setBand(e, next)} onAnswered={v => answered(e, v)} />
              );
            })}
          </ol>
        </section>
      )) : (entries.length ? null : <p className="jokbo-notes-empty">비어 있음</p>)}
    </main>
  );
}

function NoteCard({ entry, entered, index, open, band, onBand, onAnswered }: {
  entry: JokboNoteEntry; entered: "high" | "mid"; index: number; open: boolean;
  band: JokboBand | null;
  onBand: (band: Shown) => void;
  onAnswered: (verdict: Verdict) => void;
}) {
  const item = entry.item;
  const [picked, setPicked] = useState<number[]>([]);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const revealed = open || verdict !== null;
  const need = needed(item);
  const now = shownBand(band);
  const tone = RATINGS.find(r => r.key === now)?.tone ?? "fine";
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
    <li className={`quiz-card bank-card jokbo-card jokbo-note is-${tone}${now !== entered ? " is-changed-band" : ""}`}>
      <div className="jokbo-meta">
        <span className="jokbo-note-index">{index}</span>
        <span className={`jokbo-who is-${entry.kind}`}>{years.join("·")} {entry.professors.join(", ") || "교수 미상"}</span>
        <span className="jokbo-num">{item.number}번</span>
        {entry.mark.wrongCount ? <span className="jokbo-note-wrong">틀림 {entry.mark.wrongCount}</span> : null}
      </div>

      {/* 고르지 않고 「정답 보기」로 연 것은 판정이 없다. */}
      <JokboBody item={item} picked={picked} revealed={revealed} verdict={picked.length ? verdict : null}
        onPick={revealed ? undefined : pick} />

      {revealed ? null : (
        <div className="jokbo-note-actions">
          {need > 1 ? (
            <button type="button" className="quiz-submit" disabled={picked.length !== need} onClick={() => check(picked)}>확인 · {need}개</button>
          ) : null}
          <button type="button" className="pill-button" onClick={() => check([])}>정답 보기</button>
        </div>
      )}

      <RatingButtons band={band} onChange={onBand} />
    </li>
  );
}
