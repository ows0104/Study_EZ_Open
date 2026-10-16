import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { BankAnswer, BankNext, BankQuestion, BankRating } from "../types/bank";
import type { SlidePreloader } from "../slidePreload";

export type PreparedFrame = {
  next: BankNext; answer: BankAnswer; options: BankQuestion;
  previews: Partial<Record<BankRating, BankNext>>;
  origin?: { subject: string; runId: string; reviewToken: string; ratings: BankRating[] };
};

/** Cache survives consuming a question; each acknowledgement replenishes it. */
export function useBankBuffer(base: string, token: string | undefined, slides: SlidePreloader,
  revision: number, acknowledgement: number, lectures?: { subject: string; runId: string }[]) {
  const selection = JSON.stringify(lectures);
  const cache = useMemo(() => new Map<string, PreparedFrame>(), [revision, selection]);
  const [, changed] = useState(0);
  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
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
      // Preserve useful branches while replacing the current three-question window.
      const keep = new Map(cache);
      cache.clear();
      for (const [key, frame] of Object.entries(frames)) {
        const old = keep.get(key);
        if (!Object.keys(frame.previews).length && old) frame.previews = old.previews;
        cache.set(key, frame);
      }
      // Warm the current card plus three likely successors, rather than evicting
      // their images by warming every alternative rating's slides at once.
      let frame = cache.get(token);
      for (let i = 0; frame && i < 4; i++) {
        const exam = frame.answer.jokboSlides ?? [];
        const visibleExam = exam.some(slide => slide.primary) ? exam.filter(slide => slide.primary)
          : !frame.answer.evidenceStatus || frame.answer.slides.some(slide => slide.primary) ? exam : [];
        slides.warm([...(frame.next.preloadSlides ?? []), ...frame.answer.slides]
          .filter(slide => slide.primary).map(slide => slide.url).concat(visibleExam.map(slide => slide.url)));
        frame = cache.get(frame.previews.Good?.reviewToken ?? "");
      }
      changed(value => value + 1);
    }).catch(() => {}); // Older APIs and speculative tokens use the normal request path.
    return () => controller.abort();
  }, [base, token, slides, cache, selection, acknowledgement]);
  return cache;
}
