import type { NextInterval, QuizItem, QuizSchedule } from "../types/quiz";

/**
 * 다음에 낼 카드를 고른다. **안키의 큐다.**
 *
 * 일정을 **정하는** 곳은 서버(`app/srs.py`)이고 여기는 정해진 일정을 보고
 * 순서만 세운다. 간격을 이쪽에서 다시 계산하지 않는 이유는 그것이 두 곳에
 * 살게 되기 때문이다 — 버튼에 적는 「언제 다시 나오나」도 서버가 `reveal`에
 * 실어 보낸 값(`next`)을 그대로 쓴다.
 *
 * 순수 함수만 둔다. 순서를 눈으로 확인하려면 화면을 띄워야 하는 상태가
 * 되면 안 되고, `Quiz.tsx`는 이미 화면 일을 충분히 든다.
 */

/** 카드가 있을 수 있는 자리 넷. 서버의 `srs.py`와 같은 이름이다. */
export type CardState = QuizSchedule["state"];

/** 지금 무엇을 보여 줄 것인가. */
export type Pick =
  | { kind: "card"; item: QuizItem }
  /** 낼 것이 없다. **왜 없는지를 갈라서 말한다**(아래 주석). */
  | { kind: "empty"; reason: EmptyReason; nextDueAt: number | null };

/**
 * 「0장」이 왜 0인가.
 *
 * **이 셋을 한 자리에서 같은 0으로 보여 주면 사람은 「고장」으로 읽는다**
 * (`../../CLAUDE.md` 함정 ③). 재료가 없는 것과, 다 익어서 아직 때가 아닌
 * 것과, 오늘 몫을 끝낸 것은 다음에 할 일이 서로 다르다.
 *
 *   no-cards    이 편에 카드가 없다 — 파이프라인이 아직 안 냈거나 옛 편이다
 *   done-today  오늘 몫을 끝냈다 — 다음 때가 `nextDueAt`에 있다
 *   cram-done   몰아보기로 한 바퀴를 다 돌았다
 */
export type EmptyReason = "no-cards" | "done-today" | "cram-done";

export type Counts = {
  /** 한 번도 안 찍은 카드. */
  new: number;
  /**
   * 익히는 중(`learning`·`relearn`). **때가 아직 안 된 것까지 센다.**
   *
   * 그 카드는 오늘 안에 나온다 — 큐가 ④로 미리 내기 때문이다. 때를 보고
   * 갈라 세면 화면이 「남은 것 0」을 적으면서 카드를 내밀게 된다.
   */
  learning: number;
  /** 익었고 때가 된 것. */
  review: number;
  /** 익었고 아직 때가 아닌 것. **오늘은 안 나온다.** */
  later: number;
  /** 오늘 낼 것 전부. */
  due: number;
  /** 아직 때가 아닌 것 중 가장 이른 때. 없으면 `null`. */
  nextDueAt: number | null;
};

/** Current card and the next two candidates, using the same queue policy. */
export function upcoming(items: QuizItem[], now: number, options: Parameters<typeof pick>[2]): QuizItem[] {
  const result: QuizItem[] = [];
  let remaining = items;
  while (result.length < 3) {
    const next = pick(remaining, now, result.length ? { ...options, forcedId: undefined } : options);
    if (next.kind !== "card") break;
    result.push(next.item);
    remaining = remaining.filter((entry) => entry.itemId !== next.item.itemId);
  }
  return result;
}

export function stateOf(item: QuizItem): CardState {
  return item.attempt?.state ?? "new";
}

/**
 * 이 카드를 언제 내는가. 밀리초다. **일정이 없으면 지금이다.**
 *
 * `null`은 「아직 안 찍은 카드」와 「일정 칼럼이 없던 옛 줄」 둘 다에서 온다.
 * 둘 다 지금 내는 것이 맞다 — 새 카드는 원래 그렇고, 옛 줄은 사다리의 첫
 * 칸에 올려야 한다.
 */
export function dueOf(item: QuizItem): number {
  const at = item.attempt?.dueAt;
  return at ? Date.parse(at) : 0;
}

function isLearning(state: CardState): boolean {
  return state === "learning" || state === "relearn";
}

export function counts(items: QuizItem[], now: number): Counts {
  const out: Counts = { new: 0, learning: 0, review: 0, later: 0, due: 0, nextDueAt: null };
  for (const item of items) {
    const state = stateOf(item);
    if (state === "new") {
      out.new += 1;
      continue;
    }
    if (isLearning(state)) {
      // 때를 안 본다. 익히는 중인 카드는 오늘 안에 나온다(큐의 ④).
      out.learning += 1;
      continue;
    }
    const due = dueOf(item);
    if (due <= now) {
      out.review += 1;
      continue;
    }
    out.later += 1;
    if (out.nextDueAt === null || due < out.nextDueAt) out.nextDueAt = due;
  }
  out.due = out.new + out.learning + out.review;
  return out;
}

/**
 * 다음 카드.
 *
 * 순서는 안키다 — **잊기 직전의 것이 먼저다.**
 *
 *   ① 익히는 중이고 때가 된 것   (이른 것부터)
 *   ② 익었고 때가 된 것          (이른 것부터)
 *   ③ 새 카드                    (출제 순서)
 *   ④ 그래도 남은 익히는 중      때가 안 됐어도 낸다 — 아래 「미리 낸다」
 *
 * **④가 없으면 세션이 안 끝난다.** Again을 누른 카드는 1분 뒤로 잡히는데,
 * 그것이 마지막 카드였으면 화면은 1분 동안 「할 것 없음」을 보여 준다. 그
 * 1분은 사람에게 「끝났다」로 읽히고, 정작 그 카드는 모르는 카드다. 안키도
 * 덱의 끝에서 같은 일을 한다(learn ahead).
 *
 * @param forcedId 되돌리기가 세운 카드. 순서를 무시하고 이것을 낸다 —
 *   되돌린 카드가 화면에 안 서면 무엇이 되돌아갔는지 볼 수가 없다.
 * @param cram 때를 무시하고 전부 낸다. 시험 전에 몰아서 볼 때다.
 * @param seen 몰아보기에서 이미 낸 카드. **몰아보기에만 쓴다** — 때를
 *   무시하는 큐는 찍어도 카드가 안 빠지므로, 세지 않으면 한 바퀴가 안 끝난다.
 *   보통 큐에서는 빼면 안 된다: Again을 누른 카드가 그 자리에서 다시
 *   돌아오는 것이 익히기의 요점이다.
 */
export function pick(
  items: QuizItem[],
  now: number,
  {
    forcedId = "",
    cram = false,
    seen,
  }: { forcedId?: string; cram?: boolean; seen?: ReadonlySet<string> } = {},
): Pick {
  if (!items.length) return { kind: "empty", reason: "no-cards", nextDueAt: null };

  if (forcedId) {
    const forced = items.find((item) => item.itemId === forcedId);
    if (forced) return { kind: "card", item: forced };
  }

  const learning: QuizItem[] = [];
  const review: QuizItem[] = [];
  const fresh: QuizItem[] = [];
  const waiting: QuizItem[] = [];

  for (const item of items) {
    if (cram && seen?.has(item.itemId)) continue;
    const state = stateOf(item);
    if (state === "new") {
      fresh.push(item);
      continue;
    }
    if (!cram && dueOf(item) > now) {
      // 때를 기다린다. 익은 카드는 여기서 끝이고, 익히는 중인 것만 ④로 되돌아온다.
      if (isLearning(state)) waiting.push(item);
      continue;
    }
    (isLearning(state) ? learning : review).push(item);
  }

  const byDue = (a: QuizItem, b: QuizItem) => dueOf(a) - dueOf(b);
  const next =
    learning.sort(byDue)[0] ??
    review.sort(byDue)[0] ??
    fresh[0] ??
    // ④ 때가 안 됐어도 익히는 중인 것은 미리 낸다.
    waiting.sort(byDue)[0];

  if (next) return { kind: "card", item: next };
  return {
    kind: "empty",
    reason: cram ? "cram-done" : "done-today",
    nextDueAt: counts(items, now).nextDueAt,
  };
}

/**
 * 「언제 다시 나오나」를 사람 말로. **버튼에 적는 값이다.**
 *
 * `days`가 0이면 분 단위(익히는 중)이고, 아니면 날 단위(익은 카드)다. 서버가
 * 그렇게 갈라서 보내는 이유는 반올림이다 — 밤 11시에 찍은 「하루 뒤」는
 * 벽시계로 다섯 시간 뒤라, 초만 받으면 「5시간」으로 적힌다.
 */
export function intervalLabel({ days, seconds }: NextInterval): string {
  if (days >= 365) return "1년";
  if (days >= 30) return `${Math.round(days / 30)}개월`;
  if (days > 0) return `${days}일`;
  if (seconds >= 3600) return `${Math.round(seconds / 3600)}시간`;
  if (seconds >= 60) return `${Math.round(seconds / 60)}분`;
  return "곧";
}

/** 「9월 22일」. 다음 복습이 언제인지 적는 자리에 쓴다. */
export function dayLabel(at: number): string {
  return new Date(at).toLocaleDateString("ko-KR", { month: "long", day: "numeric" });
}

/** 오늘로부터 며칠 뒤인가. 학습일(한국 시간 새벽 4시 경계)만 보고 센다 — 시각까지 세면 하루가 0일이 된다. */
export function daysFromNow(at: number, now: number): number {
  const day = 24 * 60 * 60 * 1000;
  // 새벽 4시 = calendar/entries.ts `DAY_START_HOUR`. 이 파일은 단독으로 읽히는 검사가 있어 import하지 않는다.
  const studyDay = (ms: number) => Math.floor((ms + (9 - 4) * 3_600_000) / day);
  return Math.max(0, studyDay(at) - studyDay(now));
}
