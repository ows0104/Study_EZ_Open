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
    if (!token) return;
    const controller = new AbortController();
    cache.requests.add(controller);
    const request = (target: string, reviewToken: string, ratings?: BankRating[]) =>
      api<{ frames: Record<string, PreparedFrame> }>(`${target}/prepare-buffer`, {
        method: "POST", body: JSON.stringify({ reviewToken, ratings,
          lectures: selection ? JSON.parse(selection) : undefined }), signal: controller.signal,
      });
    request(base, token).catch(cause => {
      const origin = cache.get(token)?.origin;
      if (controller.signal.aborted || !origin?.ratings.length) throw cause;
      return request(`/api/lectures/${encodeURIComponent(origin.subject)}/${encodeURIComponent(origin.runId)}/bank`,
        origin.reviewToken, origin.ratings);
    }).then(({ frames }) => {
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
      // Warm the current card plus three likely successors, rather than evicting
      // their images by warming every alternative rating's slides at once.
      let frame = cache.get(visible.current ?? "");
      for (let i = 0; frame && i < 4; i++) {
        const exam = frame.answer.jokboSlides ?? [];
        const visibleExam = exam.some(slide => slide.primary) ? exam.filter(slide => slide.primary)
          : !frame.answer.evidenceStatus || frame.answer.slides.some(slide => slide.primary) ? exam : [];
        slides.warm([...(frame.next.preloadSlides ?? []), ...frame.answer.slides]
          .filter(slide => slide.primary).map(slide => slide.url).concat(visibleExam.map(slide => slide.url)));
        frame = cache.get(frame.previews.Good?.reviewToken ?? "");
      }
      changed(value => value + 1);
    }).catch(() => {}) // Older APIs and speculative tokens use the normal request path.
      .finally(() => cache.requests.delete(controller));
  }, [base, token, slides, cache, selection, acknowledgement]);
  return cache;
}
