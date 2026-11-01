import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { BankAnswer, BankNext, BankQuestion, BankRating } from "../types/bank";
import type { SlidePreloader } from "../slidePreload";

export type PreparedFrame = {
  next: BankNext; answer: BankAnswer; options: BankQuestion;
  previews: Partial<Record<BankRating, BankNext>>;
  origin?: { subject: string; runId: string; reviewToken: string; ratings: BankRating[] };
};

class FrameCache extends Map<string, PreparedFrame> {
  readonly requests = new Set<AbortController>();

  getFor(next: BankNext | null | undefined): PreparedFrame | undefined {
    const frame = this.get(next?.reviewToken ?? "");
    if (!frame || frame.next.question?.question_id !== next?.question?.question_id
      || frame.next.question?.question !== next?.question?.question
      || frame.next.question?.presentationSeed !== next?.question?.presentationSeed
      || frame.next.lecture?.subject !== next?.lecture?.subject || frame.next.lecture?.runId !== next?.lecture?.runId) return undefined;
    return frame;
  }

  ready(token: string, steps: number): boolean {
    const frame = this.get(token);
    if (!frame) return false;
    if (steps === 0) return true;
    return (["Again", "Hard", "Good", "Easy"] as BankRating[]).every(rating => {
      const next = frame.previews[rating];
      return !!next && (next.question === null || (!!next.reviewToken && this.ready(next.reviewToken, steps - 1)));
    });
  }

  readyEasy(token: string, steps: number): boolean {
    const frame = this.get(token);
    if (!frame) return false;
    if (steps === 0) return true;
    const next = frame.previews.Easy;
    return !!next && (next.question === null || (!!next.reviewToken && this.readyEasy(next.reviewToken, steps - 1)));
  }

  override clear() {
    for (const request of this.requests) request.abort();
    this.requests.clear();
    super.clear();
  }
}

/** Cache survives consuming a question; each acknowledgement replenishes it. */
export function useBankBuffer(base: string, token: string | undefined, slides: SlidePreloader,
  revision: number, acknowledgement: number, lectures?: { subject: string; runId: string }[]) {
  const selection = JSON.stringify(lectures);
  const cache = useMemo(() => new FrameCache(), [revision, selection]);
  const visible = useRef(token);
  visible.current = token;
  const [, changed] = useState(0);
  // Navigation and acknowledgements must not cancel useful work already in flight.
  // Editing, changing the selection, rollback, and unmount still invalidate it.
  useEffect(() => () => cache.clear(), [cache]);
  useEffect(() => {
    if (!token || cache.ready(token, 2) || (cache.ready(token, 1) && cache.readyEasy(token, 4))) return;
    const controller = new AbortController();
    cache.requests.add(controller);
    const request = (target: string, reviewToken: string, ratings?: BankRating[], lookahead: "near" | "full" = "full") =>
      api<{ frames: Record<string, PreparedFrame>; lookahead?: "near" | "full" }>(`${target}/prepare-buffer`, {
        method: "POST", body: JSON.stringify({ reviewToken, ratings,
          lectures: selection ? JSON.parse(selection) : undefined, lookahead }), signal: controller.signal,
      });
    const prepare = (lookahead: "near" | "full") => request(base, token, undefined, lookahead).catch(cause => {
      const origin = cache.get(token)?.origin;
      if (controller.signal.aborted || !origin?.ratings.length) throw cause;
      return request(`/api/lectures/${encodeURIComponent(origin.subject)}/${encodeURIComponent(origin.runId)}/bank`,
        origin.reviewToken, origin.ratings, lookahead);
    });
    const merge = ({ frames }: { frames: Record<string, PreparedFrame> }) => {
      if (controller.signal.aborted) return;
      // Replies can arrive out of order. Merge windows so an older, shallower
      // reply cannot discard successors or erase branches prepared by a newer one.
      for (const [key, frame] of Object.entries(frames)) {
        const old = cache.get(key);
        // A refill may not redraw an already usable frame or replace its signed
        // rating branches. The visible card and its cached answer stay paired.
        if (old && JSON.stringify(old.next.question) !== JSON.stringify(frame.next.question)) continue;
        frame.previews = { ...frame.previews, ...old?.previews };
        cache.delete(key);
        cache.set(key, frame);
      }
      // Keep memory bounded without replacing the whole usable window per reply.
      while (cache.size > 128) cache.delete(cache.keys().next().value!);
      // Warm the near alternatives too. Finish with the current card so the
      // bounded image cache retains its slides ahead of more distant branches.
      const current = cache.get(visible.current ?? "");
      const likely: PreparedFrame[] = [];
      let following = cache.get(current?.previews.Easy?.reviewToken ?? "");
      for (let i = 0; following && i < 6; i++) {
        likely.push(following);
        following = cache.get(following.previews.Easy?.reviewToken ?? "");
      }
      const alternatives = Object.values(current?.previews ?? {}).map(next => cache.get(next.reviewToken ?? ""));
      for (const frame of [...likely.reverse(), ...alternatives, current]) {
        if (!frame) continue;
        const exam = frame.answer.jokboSlides ?? [];
        const visibleExam = exam.some(slide => slide.primary) ? exam.filter(slide => slide.primary)
          : !frame.answer.evidenceStatus || frame.answer.slides.some(slide => slide.primary) ? exam : [];
        slides.warm([...(frame.next.preloadSlides ?? []), ...frame.answer.slides]
          .filter(slide => slide.primary).map(slide => slide.url).concat(visibleExam.map(slide => slide.url)));
      }
      changed(value => value + 1);
    };
    prepare(cache.has(token) ? "full" : "near").then(result => {
      merge(result);
      if (result.lookahead === "near" && !controller.signal.aborted && visible.current === token) {
        return prepare("full").then(merge);
      }
    }).catch(() => {}) // Older APIs and speculative tokens use the normal request path.
      .finally(() => cache.requests.delete(controller));
  }, [base, token, slides, cache, selection, acknowledgement]);
  return cache;
}
