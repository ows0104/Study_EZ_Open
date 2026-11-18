import type { JokboDoc, JokboItem } from "../types/jokbo";
import { otherYears, pickItems, sameItemIds, type JokboScope } from "./selection";

/**
 * 족보 모아풀기(docs/changes/2026-11-18-jokbo-mix). 여러 강의(시간표 칸)의 족보를 한 판으로.
 *
 * 문항 ID는 칸 안에서만 유일하다. 화면에서는 `<칸>~<ID>`로 바꿔 들고, 기록할 때 원래 칸·ID로 되돌린다.
 */
export type MixOrder = "spread" | "shuffle";

export type MixLane = { eventId: string; doc: JokboDoc };

/** 같은 교수 문항이 없는 강의는 「같은 교수만」을 고를 수 없다(강의 하나 화면과 같다). */
export function canSame(doc: JokboDoc): boolean {
  return sameItemIds(doc).length > 0;
}

export function effectiveScope(doc: JokboDoc, scope: JokboScope): JokboScope {
  return scope === "same" && canSame(doc) ? "same" : "more";
}

/** 강의 하나의 고른 범위. 「다른 교수까지」는 다른 교수 연도 전부. 강의 하나 화면의 pickItems 순서 그대로. */
export function laneItems(doc: JokboDoc, scope: JokboScope): JokboItem[] {
  const all = new Set(otherYears(doc).map(y => y.key));
  return pickItems(doc, effectiveScope(doc, scope), all);
}

export const mixKey = (eventId: string, itemId: string) => `${eventId}~${itemId}`;

export function splitKey(key: string): { eventId: string; itemId: string } {
  const cut = key.indexOf("~");
  return { eventId: key.slice(0, cut), itemId: key.slice(cut + 1) };
}

/** 화면용 사본: ID와 변형 묶음 이름에 칸을 붙인다(다른 강의의 같은 이름과 섞이지 않게). */
export function tagItems(eventId: string, items: JokboItem[]): JokboItem[] {
  return items.map(it => ({ ...it, id: mixKey(eventId, it.id), variantGroup: it.variantGroup ? mixKey(eventId, it.variantGroup) : undefined }));
}

/** 이어서 내야 하는 묶음: 변형 묶음은 한 덩어리, 나머지는 한 문항씩. pickItems가 이미 변형을 붙여 두었다. */
export function units(items: JokboItem[]): JokboItem[][] {
  const out: JokboItem[][] = [];
  for (const it of items) {
    const last = out[out.length - 1];
    if (last && it.variantGroup && last[0].variantGroup === it.variantGroup) last.push(it);
    else out.push([it]);
  }
  return out;
}

/**
 * 모아풀기: 강의 안 순서는 그대로, 강의의 k번째(n개 중) 묶음을 전체의 (k+½)/n 자리에 둔다.
 * 강의마다 문항 수가 달라도 처음부터 끝까지 고르게 섞인다 — 한 바퀴씩 돌리면 뒤에는 많은 강의만 남는다.
 * 같은 자리는 강의 순서(고른 순서)대로.
 */
export function spread(lanes: JokboItem[][]): JokboItem[] {
  const placed: { at: number; lane: number; k: number; unit: JokboItem[] }[] = [];
  lanes.forEach((items, lane) => {
    const list = units(items);
    list.forEach((unit, k) => placed.push({ at: (k + 0.5) / list.length, lane, k, unit }));
  });
  placed.sort((a, b) => a.at - b.at || a.lane - b.lane || a.k - b.k);
  return placed.flatMap(p => p.unit);
}

/** 섞어풀기: 강의 사이·안 모두 무작위. 변형 묶음은 쪼개지 않는다. */
export function shuffle(lanes: JokboItem[][], random: () => number = Math.random): JokboItem[] {
  const list = lanes.flatMap(units);
  for (let i = list.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [list[i], list[j]] = [list[j], list[i]];
  }
  return list.flat();
}
