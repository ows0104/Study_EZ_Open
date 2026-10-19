import { useEffect, useMemo } from "react";
import { api } from "../api";
import type { BankNext, BankRating } from "../types/bank";
import type { SlidePreloader } from "../slidePreload";
import { splitSlides } from "./BankSlides";

/** Predictions are display-only. The rate response remains authoritative. */
export function usePreparedBankNext(base: string, token: string | undefined, enabled: boolean,
  slides: SlidePreloader, revision: number, lectures?: { subject: string; runId: string }[]) {
  const selection = JSON.stringify(lectures);
  const prepared = useMemo<{ previews: Partial<Record<BankRating, BankNext>> }>(
    () => ({ previews: {} }), [base, token, revision, selection]);
  useEffect(() => {
    if (!token || !enabled) return;
    const controller = new AbortController();
    api<Partial<Record<BankRating, BankNext>>>(`${base}/prepare-next`, {
      method: "POST", body: JSON.stringify({ reviewToken: token, lectures: selection ? JSON.parse(selection) : undefined }),
      signal: controller.signal,
    }).then(previews => {
      if (controller.signal.aborted) return;
      prepared.previews = previews;
      for (const preview of Object.values(previews)) {
        slides.warm(splitSlides(preview.preloadSlides ?? []).primary.map(slide => slide.url));
      }
    }).catch(() => {});
    return () => controller.abort();
  }, [base, token, enabled, prepared, slides, selection]);
  return prepared;
}
