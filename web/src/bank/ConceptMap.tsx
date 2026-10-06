import { useEffect, useMemo, useRef, useState } from "react";
import type { BankConcept } from "../types/bank";
import { DIRECTION_LABEL } from "./labels";
import { graphLabel } from "./graphLabel";

/**
 * 개념 지도 — Quiz Bank 첫 화면 아래(2026-10-04 관리자 — 「학생 · 풀이 창 안」 · 「그래프와 카드 둘 다」).
 *
 *   위   관계 그래프. 점 = 개념(크기 = 중요도 · 색 = 내 진척), 선 = 은행의 `related_concepts`
 *   아래 개념 카드. 핵심 사실 · 방향별 숙련도(목표 눈금과 나란히) · 관련 개념
 *
 * **숫자는 서버가 낸다**(`study_engine.concept_map`). 목표치는 다음 문항을 고르는 엔진의 것과
 * 같은 값이어야 한다 — 여기서 다시 계산하면 「목표에 닿았다」는 지도와 「아직 약하다」는
 * 엔진이 서로 다른 말을 한다.
 *
 * 그래프 배치는 화면이 한다. 같은 은행과 화면 폭이면 같은 모양이 나오게 난수를 안 쓴다.
 */
export function ConceptMap({ concepts }: { concepts: BankConcept[] }) {
  const [focus, setFocus] = useState<string | null>(null);
  const sorted = useMemo(
    () => [...concepts].sort((a, b) => TIER_ORDER[a.tier] - TIER_ORDER[b.tier] || b.importance - a.importance),
    [concepts],
  );

  function pick(id: string) {
    setFocus(id);
    document.getElementById(`concept-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  return (
    <section className="bank-cmap">
      <h3>개념 지도</h3>
      <p className="bank-note">
        크기는 중요도, 색은 학습 진척입니다. 개념을 누르면 자세한 카드로 갑니다.
        숙련도는 스스로 매긴 평가로 쌓은 지수이고 정답 확률이 아닙니다.
      </p>
      <ConceptGraph concepts={concepts} focus={focus} onPick={pick} />
      <div className="bank-cmap-cards">
        {sorted.map((c) => (
          <ConceptCard key={c.concept_id} concept={c} focused={focus === c.concept_id} onPick={pick} />
        ))}
      </div>
    </section>
  );
}

const TIER_ORDER: Record<BankConcept["tier"], number> = { Core: 0, Advanced: 1, Optional: 2 };
const SIGNAL_LABEL: Record<string, string> = { high: "족보 신호 높음", medium: "족보 신호 보통", low: "족보 신호 낮음" };
const pct = (n: number) => `${Math.round(n * 100)}%`;

/** 진척(0–1)을 색으로. 0 은 빈 면, 1 은 `--ok`. 다크 모드는 토큰이 알아서 바뀐다. */
const fill = (progress: number) => `color-mix(in srgb, var(--ok) ${Math.round(progress * 85)}%, var(--surface-2))`;

type Board = { W: number; H: number };

function useBoard(count: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  useEffect(() => {
    if (!ref.current) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) setWidth(Math.round(entry.contentRect.width));
    });
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  const board = useMemo(() => {
    const W = Math.max(280, width);
    const columns = Math.max(2, Math.floor((W - 32) / 100));
    // 개념이 많거나 컨테이너가 좁으면 세로 공간을 늘려 글씨 크기를 유지한다.
    return { W, H: Math.max(380, Math.ceil(count / columns) * 100 + 48) };
  }, [width, count]);
  return { ref, board };
}

type Point = { x: number; y: number };

/** Fruchterman–Reingold. 원 위에서 시작하고 식는다 — 난수가 없어 같은 은행은 같은 모양이다. */
function layout(n: number, edges: [number, number][], { W, H }: Board): Point[] {
  const pos = Array.from({ length: n }, (_, i) => {
    const a = (2 * Math.PI * i) / Math.max(n, 1) - Math.PI / 2;
    return { x: W / 2 + Math.cos(a) * W * 0.32, y: H / 2 + Math.sin(a) * H * 0.32 };
  });
  if (n < 2) return pos.map(() => ({ x: W / 2, y: H / 2 }));
  // 0.55 에서는 261002_02 의 이름표 둘(C01·C05)이 겹쳤다.
  const k = Math.sqrt((W * H) / n) * 0.7;
  const rounds = 300;
  for (let round = 0; round < rounds; round++) {
    const step = 24 * (1 - round / rounds) + 0.5;
    const move = pos.map(() => ({ x: 0, y: 0 }));
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const dx = pos[i].x - pos[j].x;
        const dy = pos[i].y - pos[j].y;
        const d = Math.max(Math.hypot(dx, dy), 1);
        const push = (k * k) / d;
        move[i].x += (dx / d) * push;
        move[i].y += (dy / d) * push;
        move[j].x -= (dx / d) * push;
        move[j].y -= (dy / d) * push;
      }
    }
    for (const [i, j] of edges) {
      const dx = pos[i].x - pos[j].x;
      const dy = pos[i].y - pos[j].y;
      const d = Math.max(Math.hypot(dx, dy), 1);
      const pull = (d * d) / k;
      move[i].x -= (dx / d) * pull;
      move[i].y -= (dy / d) * pull;
      move[j].x += (dx / d) * pull;
      move[j].y += (dy / d) * pull;
    }
    for (let i = 0; i < n; i++) {
      // 선이 없는 점이 밖으로 밀려 나가지 않게 가운데로 약하게 당긴다.
      move[i].x += (W / 2 - pos[i].x) * 0.6;
      move[i].y += (H / 2 - pos[i].y) * 0.6;
      const len = Math.max(Math.hypot(move[i].x, move[i].y), 1e-9);
      const s = Math.min(len, step) / len;
      pos[i].x = Math.min(W - 54, Math.max(54, pos[i].x + move[i].x * s));
      pos[i].y = Math.min(H - 62, Math.max(30, pos[i].y + move[i].y * s));
    }
  }
  // 원뿐 아니라 최대 세 줄 이름표와 여백을 포함한 96×84 영역을 분리한다.
  for (let round = 0; round < 160; round++) {
    let overlap = false;
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const dx = pos[j].x - pos[i].x;
        const dy = pos[j].y - pos[i].y;
        const ox = 96 - Math.abs(dx);
        const oy = 84 - Math.abs(dy);
        if (ox <= 0 || oy <= 0) continue;
        overlap = true;
        if (ox < oy) {
          const shift = (Math.sign(dx) || 1) * (ox / 2 + 0.1);
          pos[i].x -= shift;
          pos[j].x += shift;
        } else {
          const shift = (Math.sign(dy) || 1) * (oy / 2 + 0.1);
          pos[i].y -= shift;
          pos[j].y += shift;
        }
      }
    }
    for (const p of pos) {
      p.x = Math.min(W - 54, Math.max(54, p.x));
      p.y = Math.min(H - 62, Math.max(30, p.y));
    }
    if (!overlap) break;
  }
  const crowded = pos.some((p, i) => pos.slice(i + 1).some((q) =>
    Math.abs(p.x - q.x) < 94 && Math.abs(p.y - q.y) < 82,
  ));
  if (!crowded) return pos;

  // 연결이 매우 빽빽하면 경계에서 충돌 해소가 멈출 수 있다. 이때는 원래 위치에
  // 가까운 빈 자리부터 배정해 이름표 간격이 보장되는 엇갈린 격자에 정돈한다.
  const columns = Math.max(2, Math.floor((W - 32) / 100));
  const rows = Math.ceil(n / columns);
  const slots = Array.from({ length: columns * rows }, (_, i) => ({
    x: 54 + (i % columns) * (W - 108) / (columns - 1),
    y: rows === 1 ? H / 2 : 34 + (Math.floor(i / columns) + (i % 2) * 0.15) * (H - 104) / (rows - 0.85),
  }));
  const placed: Point[] = new Array(n);
  const pending = new Set(pos.map((_, i) => i));
  while (pending.size) {
    let nearest = { node: 0, slot: 0, distance: Infinity };
    for (const node of pending) {
      slots.forEach((slot, i) => {
        const distance = Math.hypot(pos[node].x - slot.x, pos[node].y - slot.y);
        if (distance < nearest.distance) nearest = { node, slot: i, distance };
      });
    }
    placed[nearest.node] = slots.splice(nearest.slot, 1)[0];
    pending.delete(nearest.node);
  }
  return placed;
}

function ConceptGraph({ concepts, focus, onPick }: {
  concepts: BankConcept[];
  focus: string | null;
  onPick: (id: string) => void;
}) {
  const { ref, board } = useBoard(concepts.length);
  const [hovered, setHovered] = useState<string | null>(null);
  const { W, H } = board;
  const labels = useMemo(() => {
    const context = document.createElement("canvas").getContext("2d");
    if (context) context.font = `500 10.5px ${getComputedStyle(document.body).fontFamily}`;
    const measure = (text: string) => context?.measureText(text).width ?? Array.from(text).length * 10.5;
    // 같은 요약이 생기면 전체 제목을 써서 서로 다른 개념이 같은 이름으로 보이지 않게 한다.
    const titles = concepts.map((c) => c.graph_title?.trim() || c.title);
    return concepts.map((c, i) => graphLabel(
      titles.some((title, j) => j !== i && title === titles[i]) ? c.title : titles[i], measure,
    ));
  }, [concepts]);
  const { edges, pos } = useMemo(() => {
    const index = new Map(concepts.map((c, i) => [c.concept_id, i]));
    const seen = new Set<string>();
    const edges: [number, number][] = [];
    concepts.forEach((c, i) => {
      for (const r of c.related_concepts) {
        const j = index.get(r);
        if (j === undefined || j === i) continue;
        const key = i < j ? `${i}-${j}` : `${j}-${i}`;
        if (seen.has(key)) continue;
        seen.add(key);
        edges.push([i, j]);
      }
    });
    return { edges, pos: layout(concepts.length, edges, board) };
  }, [concepts, board]);

  const active = hovered ?? focus;
  const focusIndex = concepts.findIndex((c) => c.concept_id === active);
  const neighbors = new Set([focusIndex]);
  for (const [i, j] of edges) {
    if (i === focusIndex) neighbors.add(j);
    if (j === focusIndex) neighbors.add(i);
  }

  return (
    <div ref={ref} className="bank-cmap-canvas">
      <svg className="bank-cmap-graph" viewBox={`0 0 ${W} ${H}`} role="group" aria-label="개념 관계 그래프">
        {edges.map(([i, j]) => (
          <line
            key={`${i}-${j}`}
            x1={pos[i].x}
            y1={pos[i].y}
            x2={pos[j].x}
            y2={pos[j].y}
            className={focusIndex === i || focusIndex === j ? "is-focus" : focusIndex >= 0 ? "is-muted" : ""}
          />
        ))}
        {concepts.map((c, i) => {
          const r = 6 + Math.min(5, Math.max(0, c.importance)) * 1.5;
          return (
            <g
              key={c.concept_id}
              className={`bank-cmap-node${active === c.concept_id ? " is-focus" : ""}${focusIndex >= 0 && !neighbors.has(i) ? " is-muted" : ""}${c.tier === "Optional" ? " is-optional" : ""}`}
              transform={`translate(${pos[i].x} ${pos[i].y})`}
              onClick={() => onPick(c.concept_id)}
              onMouseEnter={() => setHovered(c.concept_id)}
              onMouseLeave={() => setHovered(null)}
              onFocus={() => setHovered(c.concept_id)}
              onBlur={() => setHovered(null)}
              role="button"
              aria-label={`${c.concept_id} ${c.title} · 중요도 ${c.importance} · 진척 ${pct(c.progress)}`}
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onPick(c.concept_id);
                }
              }}
            >
              <title>
                {c.concept_id} {c.title} · 중요도 {c.importance} · 진척 {pct(c.progress)}
              </title>
              <circle className="bank-cmap-hit" r={22} />
              <circle className="bank-cmap-dot" r={r} style={{ fill: fill(c.progress) }} />
              <text className="bank-cmap-label" y={r + 16}>
                {labels[i].map((line, index) => (
                  <tspan key={index} x={0} dy={index === 0 ? 0 : 12}>{line}</tspan>
                ))}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function ConceptCard({ concept: c, focused, onPick }: {
  concept: BankConcept;
  focused: boolean;
  onPick: (id: string) => void;
}) {
  return (
    <article id={`concept-${c.concept_id}`} className={`bank-cmap-card${focused ? " is-focus" : ""}`}>
      <header>
        <strong>
          {c.concept_id} {c.title}
        </strong>
        <span className="bank-cmap-meta">
          {c.tier} · 중요도 {c.importance} · 난이도 {c.concept_difficulty}
          {SIGNAL_LABEL[c.exam_signal_strength] ? ` · ${SIGNAL_LABEL[c.exam_signal_strength]}` : ""}
        </span>
      </header>
      {c.core_facts.length ? (
        <ul className="bank-cmap-facts">
          {c.core_facts.map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      ) : null}
      {c.importance_rationale ? <p className="bank-cmap-why">왜 중요한가 — {c.importance_rationale}</p> : null}
      <div className="bank-cmap-dirs">
        {c.directions.map((d) => (
          <div key={d.direction} className="bank-cmap-dir" title={`${d.questions}문항 · 평가 ${d.reviews}번`}>
            <span>{DIRECTION_LABEL[d.direction] ?? d.direction}</span>
            <span className="bank-cmap-bar">
              <span className="bank-cmap-fill" style={{ width: pct(Math.min(d.mastery, 1)) }} />
              <span className="bank-cmap-target" style={{ left: pct(Math.min(d.target, 1)) }} />
            </span>
            <small>
              {pct(d.mastery)} / {pct(d.target)}
            </small>
          </div>
        ))}
      </div>
      {c.related_concepts.length ? (
        <p className="bank-cmap-related">
          관련{" "}
          {c.related_concepts.map((id) => (
            <button key={id} className="is-quiet" onClick={() => onPick(id)}>
              {id}
            </button>
          ))}
        </p>
      ) : null}
    </article>
  );
}
