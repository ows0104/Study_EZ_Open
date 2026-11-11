import { useEffect, useState } from "react";
import { api } from "../api";
import type { RootOverview, RootQuestionProgress, RootSummary } from "../types/rootLearning";

type Catalog = { lectures: (RootOverview & { subject: string; runId: string })[] };
export type RootCatalog = Map<string, RootSummary | null>;

/**
 * 이 계정에 열린 Main-Quiz의 학습 목표 요약. 키는 `과목/runId`.
 *
 * 캘린더 칸마다·강의 목록·패널이 같은 값을 쓰므로 한 번만 묻고 잠시 나눠 쓴다.
 * 서버는 강의마다 요약을 계산하므로(약 1초) Main-Quiz가 있는 화면에서만 부른다.
 * 실패하면 빈 지도 — 막대가 회색으로 남을 뿐 화면은 그대로다.
 */
let cached: { at: number; value: Promise<Catalog["lectures"]> } | null = null;
const FRESH_MS = 60_000;

function fetchCatalog(): Promise<Catalog["lectures"]> {
  if (cached && Date.now() - cached.at < FRESH_MS) return cached.value;
  const value = api<Catalog>("/api/root-learning")
    .then(v => v.lectures ?? [])
    .catch(() => { cached = null; return []; });
  cached = { at: Date.now(), value };
  return value;
}

const keyOf = (r: { subject: string; runId: string }) => `${r.subject}/${r.runId}`;
const load = (): Promise<RootCatalog> => fetchCatalog().then(rows => new Map(rows.map(r => [keyOf(r), r.summary] as const)));
const loadProgress = (): Promise<RootProgressCatalog> => fetchCatalog()
  .then(rows => new Map(rows.flatMap(r => r.questionProgress ? [[keyOf(r), r.questionProgress] as const] : [])));

/** 강의 목록 카드 열의 Main-Quiz 문항 수(같은 요청을 나눠 쓴다). */
export type RootProgressCatalog = Map<string, RootQuestionProgress>;
export function useRootProgress(enabled = true): RootProgressCatalog {
  return useShared(loadProgress, enabled);
}

export function useRootCatalog(enabled = true): RootCatalog {
  return useShared(load, enabled);
}

function useShared<T extends Map<string, unknown>>(read: () => Promise<T>, enabled: boolean): T {
  const [rows, setRows] = useState<T>(() => new Map() as T);
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    const refresh = () => void read().then(v => { if (live) setRows(v); });
    refresh();
    // 풀이 창에서 돌아오면 새 기록으로 다시 읽는다(캐시가 지났을 때만 실제 요청).
    window.addEventListener("focus", refresh);
    return () => { live = false; window.removeEventListener("focus", refresh); };
  }, [enabled]);
  return rows;
}

/** Main-Quiz 학습률. 서버 `root_learning/score.py`가 계산한 값을 그대로 쓴다(웹에서 다시 계산하지 않는다).
 *  강의 목록·캘린더·패널·시험 계획이 같은 값이다. */
export function rootRate(summary: RootSummary | null | undefined): number | null {
  return summary?.score ?? null;
}
