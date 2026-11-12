import { useEffect, useState } from "react";
import { api } from "../api";
import type { RootOverview, RootQuestionProgress, RootSummary } from "../types/rootLearning";
import { OPTIONAL_EVENT, useOptionalVersion } from "./optionalExclusion";

type Catalog = { lectures: (RootOverview & { subject: string; runId: string })[] };
export type RootCatalog = Map<string, RootSummary | null>;
/** 강의 목록 카드 열의 Main-Quiz 문항 수. */
export type RootProgressCatalog = Map<string, RootQuestionProgress>;
export type RootSummaries = { rates: RootCatalog; progress: RootProgressCatalog; loaded: boolean };

/**
 * 이 계정에 열린 Main-Quiz의 학습 목표 요약. 키는 `과목/runId`.
 *
 * 서버가 강의마다 요약·계획을 계산하므로 느리다(운영 2026-11-12: 6.5–8.8 s, 배포 직후 더 길다).
 * 강의 목록은 이 응답을 기다리지 않고 그리고, 숫자 칸만 채운다. 한 번 묻고 60초 나눠 쓴다.
 * 실패하면 빈 지도 — 숫자 칸이 「—」로 남을 뿐 화면은 그대로다.
 */
let cached: { at: number; value: Promise<Catalog["lectures"]> } | null = null;
const FRESH_MS = 60_000;
// Optional 계산 제외가 바뀌면 캐시를 버린다(화면의 effect보다 먼저 등록돼 먼저 돈다).
window.addEventListener(OPTIONAL_EVENT, () => { cached = null; });

function fetchCatalog(): Promise<Catalog["lectures"]> {
  if (cached && Date.now() - cached.at < FRESH_MS) return cached.value;
  const value = api<Catalog>("/api/root-learning")
    .then(v => v.lectures ?? [])
    .catch(() => { cached = null; return []; });
  cached = { at: Date.now(), value };
  return value;
}

/** 시간표와 같이 출발시킨다. 행이 그려진 뒤에 묻기 시작하면 그만큼 늦다. */
export function prefetchRootCatalog() {
  void fetchCatalog();
}

const keyOf = (r: { subject: string; runId: string }) => `${r.subject}/${r.runId}`;
const read = (): Promise<Omit<RootSummaries, "loaded">> => fetchCatalog().then(rows => ({
  rates: new Map(rows.map(r => [keyOf(r), r.summary] as const)),
  progress: new Map(rows.flatMap(r => r.questionProgress ? [[keyOf(r), r.questionProgress] as const] : [])),
}));

const none: RootSummaries = { rates: new Map(), progress: new Map(), loaded: false };

/** 학습률(`summary.score`)과 문항 단계 수를 한 요청으로. `loaded` 전에는 숫자 칸을 「…」로 둔다. */
export function useRootSummaries(enabled = true): RootSummaries {
  const [value, setValue] = useState<RootSummaries>(none);
  const optional = useOptionalVersion();
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    const refresh = () => void read().then(v => { if (live) setValue({ ...v, loaded: true }); });
    refresh();
    // 풀이 창에서 돌아오면 새 기록으로 다시 읽는다(캐시가 지났을 때만 실제 요청). 다시 읽는 동안은 앞 값을 둔다.
    window.addEventListener("focus", refresh);
    return () => { live = false; window.removeEventListener("focus", refresh); };
  }, [enabled, optional]);
  return value;
}

/** Main-Quiz 학습률. 서버 `root_learning/score.py`가 계산한 값을 그대로 쓴다(웹에서 다시 계산하지 않는다).
 *  강의 목록·캘린더·패널·시험 계획이 같은 값이다. */
export function rootRate(summary: RootSummary | null | undefined): number | null {
  return summary?.score ?? null;
}
