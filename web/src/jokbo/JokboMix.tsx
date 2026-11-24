import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { Icon } from "../shell/icons";
import type { JokboItem, JokboMark, JokboResponse } from "../types/jokbo";
import { readJokboMix } from "../bank/mixLinks";
import { useMarkWriter } from "./marks";
import { JokboSolve, lectureTitle } from "./JokboPage";
import { professorsOf, defaultScope, type JokboScope } from "./selection";
import { canSame, effectiveScope, laneItems, mixKey, shuffle, splitKey, spread, tagItems, type MixOrder } from "./mixOrder";
import "../bank/main-quiz.css";
import "../bank/root-batch.css";
import "../lecture/prequiz.css";
import "./jokbo.css";

/**
 * 족보 모아풀기(docs/changes/2026-11-18-jokbo-mix, 사용자 「모든 족보를 묶어서 푸는 기능」).
 *
 * 시작 화면: 같은 교수만/다른 교수까지(전체 + 강의별), 모아풀기(강의 수에 맞춰 고르게 배분)/섞어풀기.
 * 풀이·끝 화면은 강의 하나 족보(`JokboSolve`)를 그대로 쓴다. 채점·오답노트 표시·회독은 그 문항의 시간표 칸으로 간다.
 */

type Lane = { eventId: string; data?: JokboResponse; error?: string };

export function JokboMixPage() {
  const [search] = useSearchParams();
  const eventIds = useMemo(() => readJokboMix(search), [search]);
  return <Mix key={eventIds.join(",")} eventIds={eventIds} />;
}

function Mix({ eventIds }: { eventIds: string[] }) {
  const navigate = useNavigate();
  const [lanes, setLanes] = useState<Lane[]>(() => eventIds.map(eventId => ({ eventId })));
  const [loading, setLoading] = useState(true);
  const [scopes, setScopes] = useState<Record<string, JokboScope>>({});
  const [order, setOrder] = useState<MixOrder>("spread");
  const [perLecture, setPerLecture] = useState(false);
  const [queue, setQueue] = useState<JokboItem[] | null>(null);
  const [round, setRound] = useState(0);
  // 시작 화면에서 고른 범위 전부. 이것을 통째로 푼 판만 회독으로 센다(강의마다 1).
  const range = useRef<{ items: JokboItem[]; events: string[] } | null>(null);
  const { bands, setBands, answered, rate, unanswer } = useMarkWriter(splitKey);

  useEffect(() => { document.title = "족보 모아풀기 · Study_EZ"; }, []);

  useEffect(() => {
    let alive = true;
    void Promise.all(eventIds.map(async (eventId): Promise<Lane> => {
      try {
        const data = await api<JokboResponse>(`/api/jokbo/events/${encodeURIComponent(eventId)}`);
        // 표시를 못 읽어도 풀 수는 있다.
        const got = await api<{ marks: JokboMark[] }>(`/api/jokbo/marks?eventId=${encodeURIComponent(eventId)}`).catch(() => ({ marks: [] as JokboMark[] }));
        if (alive) setBands(prev => ({ ...Object.fromEntries(got.marks.map(m => [mixKey(eventId, m.itemId), m.band])), ...prev }));
        return { eventId, data };
      } catch (cause) {
        return { eventId, error: cause instanceof ApiError && cause.status === 404 ? "족보 없음" : (cause as Error).message };
      }
    })).then(read => { if (alive) { setLanes(read); setLoading(false); } });
    return () => { alive = false; };
  }, [eventIds]);

  const live = lanes.filter((l): l is Lane & { data: JokboResponse } => Boolean(l.data));
  const scopeOf = (l: Lane & { data: JokboResponse }): JokboScope => scopes[l.eventId] ?? defaultScope(l.data.doc);
  // 2026-11-24 「5시간 안에 푼 문제 빼기」 제거(사용자 지시): 고른 범위 전부를 낸다.
  const itemsOf = (l: Lane & { data: JokboResponse }, scope = scopeOf(l)) => laneItems(l.data.doc, scope);
  const total = live.reduce((n, l) => n + itemsOf(l).length, 0);
  // 전체 칩: 「같은 교수만」을 고를 수 있는 강의들 기준. 같은 교수 문항이 없는 강의는 늘 「다른 교수까지」라 세지 않는다.
  const choosable = live.filter(l => canSame(l.data.doc));
  const sameOn = choosable.filter(l => scopeOf(l) === "same").length;
  const state = (scope: JokboScope): boolean | "mixed" => {
    if (!choosable.length) return scope === "more";
    const n = scope === "same" ? sameOn : choosable.length - sameOn;
    return n === choosable.length ? true : n ? "mixed" : false;
  };
  const setEverywhere = (scope: JokboScope) => setScopes(old => ({ ...old, ...Object.fromEntries(choosable.map(l => [l.eventId, scope])) }));

  const lookup = useMemo(() => new Map(live.map(l => [l.eventId, l.data.doc])), [live]);
  const titleOf = useCallback((item?: JokboItem) => {
    if (!item) return `족보 모아풀기 · ${live.length}개 강의`;
    const doc = lookup.get(splitKey(item.id).eventId);
    return doc ? lectureTitle(doc) : "";
  }, [lookup, live.length]);
  const whoOf = useCallback((item: JokboItem) => {
    const { eventId, itemId } = splitKey(item.id);
    const doc = lookup.get(eventId);
    return doc ? professorsOf(doc, itemId) : { kind: "unknown", professors: [] };
  }, [lookup]);

  function begin() {
    const parts = live.map(l => tagItems(l.eventId, itemsOf(l)));
    const items = order === "spread" ? spread(parts) : shuffle(parts);
    if (!items.length) return;
    range.current = { items, events: live.filter((_, i) => parts[i].length).map(l => l.eventId) };
    setQueue(items); setRound(r => r + 1);
  }
  const retry = (items: JokboItem[]) => { setQueue(items); setRound(r => r + 1); };
  const finished = useCallback(() => {
    for (const eventId of range.current?.events ?? [])
      api(`/api/jokbo/events/${encodeURIComponent(eventId)}/rounds`, { method: "POST" }).catch(() => { /* 회독 기록 실패는 끝 화면을 막지 않는다 */ });
  }, []);

  const back = () => (window.history.state?.idx > 0 ? navigate(-1) : navigate("/study"));
  const count = (n: number) => n.toLocaleString("ko-KR");
  const chip = (key: string, label: string, n: number, pressed: boolean | "mixed", disabled: boolean, onClick: () => void) =>
    <button key={key} type="button" aria-pressed={pressed} disabled={disabled} onClick={onClick}
      className={[n ? "" : "is-empty", pressed === "mixed" ? "is-some" : ""].filter(Boolean).join(" ") || undefined}>
      {pressed === true && <Icon.check />}{label}<b>{count(n)}</b></button>;

  if (queue) return (
    <main className="main-quiz-learning jokbo-learning">
      <JokboSolve key={round} items={queue} bands={bands} titleOf={titleOf} hideableTitle whoOf={whoOf}
        onExit={() => setQueue(null)} onLeave={back} onRetry={retry} onAnswered={answered} onRate={rate} onUnanswer={unanswer}
        onFinish={queue === range.current?.items ? finished : undefined} />
    </main>
  );

  return (
    <main className="main-quiz-learning jokbo-learning is-start mq-mix">
      <section className="mq-start jokbo-start">
        <header className="page-head mq-head"><div>
          <p className="mq-kicker">
            <button type="button" className="quiz-back" onClick={back}>
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10 3 5 8l5 5" /></svg>뒤로
            </button>
            <span className="mq-badge jokbo-badge">족보</span>
          </p>
          <h1>족보 모아풀기 · {eventIds.length}개 강의</h1>
        </div></header>
        {!eventIds.length ? <p className="notice">고른 강의가 없습니다. <Link to="/study">강의 목록</Link>에서 강의를 체크하세요.</p> : <>
          <section className="mq-today mq-mix-options jokbo-scope" aria-label="족보 모아풀기 시작">
            <div className="mq-today-text">
              <div className="mq-mix-tiers">
                <div className="mq-focus" role="group" aria-label="교수">
                  {chip("same", "같은 교수만", live.reduce((n, l) => n + itemsOf(l, "same").length, 0), state("same"),
                    loading || !choosable.length, () => setEverywhere("same"))}
                  {chip("more", "다른 교수까지", live.reduce((n, l) => n + itemsOf(l, "more").length, 0), state("more"),
                    loading || !live.length, () => setEverywhere("more"))}
                </div>
                <button type="button" className="mq-mix-expand" aria-expanded={perLecture} aria-controls="jokbo-mix-lectures"
                  disabled={!live.length} onClick={() => setPerLecture(v => !v)}>강의별<Icon.chevronDown /></button>
              </div>
              <div className="mq-mix-modes">
                <div className="mq-mode" role="radiogroup" aria-label="문항 순서">
                  {([["spread", "모아풀기"], ["shuffle", "섞어풀기"]] as [MixOrder, string][]).map(([value, label]) =>
                    <button key={value} type="button" role="radio" aria-checked={order === value} className={order === value ? "is-on" : ""}
                      onClick={() => setOrder(value)}>{label}</button>)}
                </div>
              </div>
            </div>
            <button className="mq-start-button" disabled={loading || !total} onClick={begin}>
              <Icon.play />시작<span className="mq-card-count" aria-label={`문제 ${total}개`}>{loading ? "…" : count(total)}</span>
            </button>
          </section>
          <ul className="mq-mix-list" id="jokbo-mix-lectures" aria-label="고른 강의">
            {lanes.map(l => {
              const n = l.data ? itemsOf(l as Lane & { data: JokboResponse }).length : 0;
              const doc = l.data?.doc;
              return <li key={l.eventId} className={l.error || !n ? "is-off" : undefined}>
                <span className="mq-mix-title">{doc ? lectureTitle(doc) : l.eventId}</span>
                <span className="mq-mix-count">{loading ? "…" : l.error ?? `${count(n)}문항`}</span>
                {perLecture && l.data && doc ? <div className="mq-focus mq-mix-lane-tiers" role="group" aria-label={`${lectureTitle(doc)} 교수`}>
                  {(["same", "more"] as JokboScope[]).map(scope => {
                    const lane = l as Lane & { data: JokboResponse };
                    // 같은 교수 문항이 없는 강의의 「같은 교수만」은 0이고 꺼져 있다(늘 「다른 교수까지」).
                    return chip(scope, scope === "same" ? "같은 교수만" : "다른 교수까지",
                      scope === "same" && !canSame(doc) ? 0 : itemsOf(lane, scope).length,
                      effectiveScope(doc, scopeOf(lane)) === scope,
                      scope === "same" && !canSame(doc),
                      () => setScopes(old => ({ ...old, [l.eventId]: scope })));
                  })}
                </div> : null}
              </li>;
            })}
          </ul>
          <p><Link to="/study">강의 다시 선택</Link></p>
        </>}
      </section>
    </main>
  );
}
