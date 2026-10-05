import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { DeckKind } from "../types/jobs";

/**
 * 어느 편에 덱이 있고 무엇을 받아 갔나. **모아받기 버튼이 보는 유일한 값이다.**
 *
 * 학기 전체를 한 번에 받아 둔다(400줄쯤). 하루 버튼은 날짜 머리마다 서므로
 * 날짜별로 물으면 한 주를 그리는 데 열 번을 부른다.
 *
 * **캘린더의 `marks`·`grabbed` 로는 못 센다.** 거기 `marks.prequiz` 는 덱이
 * 아니라 웹 문항이 있어도 참이고, `grabbed.pre` 는 작년 필기만 받아도 참이다.
 * 둘 다 자리 하나에 여러 종류를 묶은 값이라 **덱만 골라 셀 수가 없다** —
 * 그것으로 세면 덱이 없는 편이 목록에 들고, 받은 적 없는 덱이 빠진다.
 */
export type BundleDeck = {
  subject: string;
  runId: string;
  /** `YYYY-MM-DD`. 캘린더의 날짜 키와 같은 꼴이다. */
  date: string;
  slot: number;
  title: string;
  kind: DeckKind;
  filename: string;
  sizeBytes: number;
  /** 이 사람이 이 덱을 받아 갔는가. 「안 받은 것만」이 이 값을 읽는다. */
  grabbed: boolean;
};

/** 버튼이 담으려는 범위. 사람이 보는 말로 하면 「하루」와 「블럭」이다. */
export type BundleScope =
  | { kind: "day"; date: string }
  | { kind: "subject"; subject: string };

/**
 * 덱 목록을 한 번 받아 두고, 받아 간 뒤에는 다시 읽는다.
 *
 * **`CalendarPage` 한 곳에서만 부른다.** 날짜 머리 다섯과 열려 있는 패널이 같은
 * 값을 봐야 하고, 칸마다 훅을 걸면 강의 수만큼 요청이 붙는다.
 */
export function useBundleDecks() {
  const [decks, setDecks] = useState<BundleDeck[] | null>(null);
  const [error, setError] = useState("");

  const reload = useCallback(() => {
    api<{ decks: BundleDeck[] }>("/api/bundles/decks")
      .then((answer) => {
        setDecks(answer.decks);
        setError("");
      })
      .catch((cause: Error) => setError(cause.message));
  }, []);

  useEffect(reload, [reload]);
  return { decks, error, reload };
}

/**
 * 이 범위 · 이 갈래의 덱들. 순서는 서버가 준 대로(날짜 → 교시)다.
 *
 * **아직 안 받은 것이 위로 오게 정렬하지 않는다.** 한 파일로 나갈 것이라 순서가
 * 눈에 보이지 않고, 여기서 흔들면 「12편」이라고 적힌 목록과 실제로 담기는 것의
 * 순서가 달라져 진행 줄이 엉뚱한 편 이름을 말한다.
 */
export function decksIn(all: BundleDeck[], scope: BundleScope, kind: DeckKind): BundleDeck[] {
  return all.filter(
    (deck) =>
      deck.kind === kind &&
      (scope.kind === "day" ? deck.date === scope.date : deck.subject === scope.subject),
  );
}

/** 한 범위의 셈 셋. 버튼이 무엇을 말할지가 전부 이것으로 갈린다. */
export type BundleTally = {
  total: number;
  /** 아직 안 받은 것. 0 이면 버튼이 「다 받았습니다」로 눕는다. */
  fresh: number;
  /** 이번에 담을 것의 크기. **안 받은 것만 센다.** */
  freshBytes: number;
};

export function tally(decks: BundleDeck[]): BundleTally {
  const fresh = decks.filter((deck) => !deck.grabbed);
  return {
    total: decks.length,
    fresh: fresh.length,
    freshBytes: fresh.reduce((sum, deck) => sum + deck.sizeBytes, 0),
  };
}

/**
 * 이 범위에 붙일 파일 이름. 확장자는 부르는 쪽이 붙인다.
 *
 * 하루는 날짜로, 블럭은 과목 이름으로 선다. **Anki 가 파일 이름을 안 읽으므로**
 * (덱 이름은 안에 들어 있다) 이것은 오직 내려받기 폴더에서 사람이 알아보라고
 * 있는 값이다.
 */
export function bundleName(scope: BundleScope, kind: DeckKind, onlyFresh: boolean): string {
  const what = kind === "pre" ? "예습" : "복습";
  const where = scope.kind === "day" ? scope.date : scope.subject;
  return `${where} ${what}${onlyFresh ? " (새로 나온 것)" : ""}`;
}
