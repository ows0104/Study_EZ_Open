import { useEffect, useMemo } from "react";
import { api } from "../api";
import type { BankAnswer } from "../types/bank";
import type { SlidePreloader } from "../slidePreload";

/** Preparation never records a reveal. Each served token owns its own cache. */
export function usePreparedBankAnswer(base: string, token: string | undefined, slides: SlidePreloader) {
  const prepared = useMemo<{ answer: BankAnswer | null }>(() => ({ answer: null }), [base, token]);
  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    api<BankAnswer>(`${base}/prepare`, {
      method: "POST", body: JSON.stringify({ reviewToken: token }), signal: controller.signal,
    }).then((answer) => {
      if (controller.signal.aborted) return;
      prepared.answer = answer;
      slides.warm(answer.slides.map((slide) => slide.url));
    }).catch(() => {}); // A miss (or older API) falls back to the normal reveal.
    return () => controller.abort();
  }, [base, token, prepared, slides]);
  return prepared;
}
