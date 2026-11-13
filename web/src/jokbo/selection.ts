import type { JokboDoc, JokboItem } from "../types/jokbo";

/**
 * 족보 진입 화면의 고르기(2026-11-13 사용자 지시).
 *
 * 「같은 교수만」 · 「다른 교수까지」. 「다른 교수까지」를 고르면 같은 교수가 아닌
 * 연도가 「2020 석승혁」처럼 하나씩 버튼으로 서고, 「전체」가 그 전부를 켜고 끈다.
 * 같은 교수 문항은 「다른 교수까지」에서도 항상 들어간다.
 */
export type JokboScope = "same" | "more";

/** 같은 교수가 아닌 한 해의 한 출제 구획. 버튼 하나다. */
export type OtherYear = {
  key: string;
  label: string;
  year: string;
  professors: string[];
  itemIds: string[];
};

export function sameItemIds(doc: JokboDoc): string[] {
  return doc.sections.filter(s => s.kind === "same").flatMap(s => s.itemIds);
}

export function otherYears(doc: JokboDoc): OtherYear[] {
  const byId = new Map(doc.items.map(it => [it.id, it]));
  const out: OtherYear[] = [];
  for (const section of doc.sections) {
    if (section.kind === "same") continue;
    for (const year of section.years) {
      const ids = section.itemIds.filter(id => byId.get(id)?.yearLabel === year);
      if (!ids.length) continue;
      const who = section.professors.length ? section.professors.join(", ") : "교수 미상";
      out.push({ key: `${year}|${section.professors.join(",")}`, label: `${year} ${who}`, year, professors: section.professors, itemIds: ids });
    }
  }
  // 최신 연도부터. 같은 해에 교수가 둘이면 원래 구획 순서.
  return out.map((y, i) => ({ y, i })).sort((a, b) => b.y.year.localeCompare(a.y.year) || a.i - b.i).map(({ y }) => y);
}

/** 고른 범위의 문항. 같은 교수 → 고른 다른 교수 연도(최신부터) 순서. */
export function pickItems(doc: JokboDoc, scope: JokboScope, years: Set<string>): JokboItem[] {
  const byId = new Map(doc.items.map(it => [it.id, it]));
  const ids = [...sameItemIds(doc)];
  if (scope === "more") for (const y of otherYears(doc)) if (years.has(y.key)) ids.push(...y.itemIds);
  return ids.map(id => byId.get(id)).filter((it): it is JokboItem => Boolean(it));
}

/** 같은 교수 문항이 없으면(교수가 바뀐 강의·CBL) 처음부터 「다른 교수까지」·전체다. */
export function defaultScope(doc: JokboDoc): JokboScope {
  return sameItemIds(doc).length ? "same" : "more";
}

export type Verdict = "correct" | "wrong" | "ungraded";

/**
 * 고른 선지의 채점. `answers`는 1부터 센다.
 * one_of 는 인정 답 중 하나만 맞으면, all_of 는 인정 답 전부를 정확히 골라야 맞다.
 * 전원 정답은 무엇이든 맞고, 답안지에 답이 없으면 채점하지 않는다.
 */
export function grade(item: JokboItem, picked: number[]): Verdict {
  if (item.answerStatus === "missing") return "ungraded";
  if (item.answerStatus === "all-correct") return picked.length ? "correct" : "wrong";
  const set = new Set(picked);
  if (item.answerMode === "all_of") {
    return set.size === item.answers.length && item.answers.every(a => set.has(a)) ? "correct" : "wrong";
  }
  return picked.length === 1 && item.answers.includes(picked[0]) ? "correct" : "wrong";
}

/** 몇 개를 골라야 확인할 수 있나. one_of 는 1, all_of 는 인정 답 수. */
export function needed(item: JokboItem): number {
  return item.answerMode === "all_of" && item.answers.length > 1 ? item.answers.length : 1;
}

/** 그 문항의 출제 교수(구획에서). */
export function professorsOf(doc: JokboDoc, itemId: string): { kind: string; professors: string[] } {
  const s = doc.sections.find(sec => sec.itemIds.includes(itemId));
  return { kind: s?.kind ?? "unknown", professors: s?.professors ?? [] };
}
