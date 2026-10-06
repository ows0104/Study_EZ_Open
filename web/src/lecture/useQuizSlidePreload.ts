import { useEffect, useMemo } from "react";
import { api } from "../api";
import { SlidePreloader } from "../slidePreload";

/** Image-only lookahead: revealing and grading still happen on user action. */
export function useQuizSlidePreload(base: string, itemIds: string[]) {
  const preload = useMemo(() => new SlidePreloader(), [base]);
  const ids = JSON.stringify(itemIds.slice(0, 3));
  useEffect(() => {
    if (ids === "[]") return;
    const controller = new AbortController();
    api<{ urls: string[] }>(`${base}/slides`, {
      method: "POST", body: JSON.stringify({ itemIds: JSON.parse(ids) }), signal: controller.signal,
    }).then(({ urls }) => {
      if (!controller.signal.aborted) preload.warm(urls);
    }).catch(() => {}); // Speculation must never prevent answering (including older APIs).
    return () => controller.abort();
  }, [base, ids, preload]);
  return preload;
}
