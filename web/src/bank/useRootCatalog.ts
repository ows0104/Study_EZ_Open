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
 * 물은 Main-Quiz 강의의 학습 목표 요약. 키는 `과목/runId`.
 *
 * 서버가 강의마다 요약·계획을 계산하므로 강의 수만큼 느리다(강의 하나 약 0.2 s).
 * 열린 강의 전부를 물을 때는 운영 2026-11-23 중앙값이 8.1 s였다(42편).
 * 그래서 강의 목록은 고른 블럭의 강의만 묻는다(docs/changes/2026-11-24-lecture-list-block-scope).
 * 목록은 이 응답을 기다리지 않고 그리고, 숫자 칸만 채운다. 같은 키 묶음은 한 번 묻고 60초 나눠 쓴다.
 * 실패하면 빈 지도 — 숫자 칸이 「—」로 남을 뿐 화면은 그대로다.
 */
const cached = new Map<string, { at: number; value: Promise<Catalog["lectures"]> }>();
const FRESH_MS = 60_000;
// Optional 계산 제외가 바뀌면 캐시를 버린다(화면의 effect보다 먼저 등록돼 먼저 돈다).
window.addEventListener(OPTIONAL_EVENT, () => { cached.clear(); });

/** `signature`는 정렬한 키를 줄바꿈으로 이은 것. 키에 줄바꿈은 없다. */
function fetchCatalog(signature: string): Promise<Catalog["lectures"]> {
  const hit = cached.get(signature);
  if (hit && Date.now() - hit.at < FRESH_MS) return hit.value;
  const query = new URLSearchParams(signature.split("\n").map(key => ["lecture", key]));
  const value = api<Catalog>(`/api/root-learning?${query}`)
    .then(v => v.lectures ?? [])
    .catch(() => { cached.delete(signature); return []; });
  cached.set(signature, { at: Date.now(), value });
  return value;
}

const keyOf = (r: { subject: string; runId: string }) => `${r.subject}/${r.runId}`;
const read = (signature: string): Promise<Omit<RootSummaries, "loaded">> => fetchCatalog(signature).then(rows => ({
  rates: new Map(rows.map(r => [keyOf(r), r.summary] as const)),
  progress: new Map(rows.flatMap(r => r.questionProgress ? [[keyOf(r), r.questionProgress] as const] : [])),
}));

const none: RootSummaries = { rates: new Map(), progress: new Map(), loaded: false };

/**
 * `keys`(`과목/runId`) 강의의 학습률(`summary.score`)과 문항 단계 수를 한 요청으로.
 * 키가 없으면 묻지 않는다. 키 묶음이 바뀌면 새로 묻고, 그동안은 `loaded: false`(숫자 칸 「…」)다 —
 * 앞 블럭의 값을 새 블럭에 쓰지 않는다.
 */
export function useRootSummaries(keys: string[]): RootSummaries {
  const signature = [...new Set(keys)].sort().join("\n");
  const [value, setValue] = useState<RootSummaries & { signature: string }>({ ...none, signature: "" });
  const optional = useOptionalVersion();
  useEffect(() => {
    if (!signature) return;
    let live = true;
    const refresh = () => void read(signature).then(v => { if (live) setValue({ ...v, loaded: true, signature }); });
    refresh();
    // 풀이 창에서 돌아오면 새 기록으로 다시 읽는다(캐시가 지났을 때만 실제 요청). 다시 읽는 동안은 앞 값을 둔다.
    window.addEventListener("focus", refresh);
    return () => { live = false; window.removeEventListener("focus", refresh); };
  }, [signature, optional]);
  return value.signature === signature ? value : none;
}

/** Main-Quiz 학습률. 서버 `root_learning/score.py`가 계산한 값을 그대로 쓴다(웹에서 다시 계산하지 않는다).
 *  강의 목록·캘린더·패널·시험 계획이 같은 값이다. */
export function rootRate(summary: RootSummary | null | undefined): number | null {
  return summary?.score ?? null;
}
