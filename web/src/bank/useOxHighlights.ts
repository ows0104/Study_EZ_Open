import { useEffect, useState } from "react";
import { oxHighlights } from "./oxHighlights";

type Range = { start: number; end: number };
type Highlights = Record<string, readonly (readonly [number, number])[]>;

/** Hash the exact visible explanation; text edits invalidate old annotations. */
export async function findOxHighlights(text: string, annotations: Highlights = oxHighlights): Promise<Range[]> {
  if (!text) return [];
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  const key = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
  return (annotations[key] ?? []).filter(([start, end]) =>
    Number.isInteger(start) && Number.isInteger(end) && start >= 0 && start < end && end <= text.length
  ).map(([start, end]) => ({ start, end }));
}

export function useOxHighlights(text: string): Range[] {
  const [selection, setSelection] = useState<{ text: string; ranges: Range[] }>({ text: "", ranges: [] });
  useEffect(() => {
    if (!text) return;
    let current = true;
    void findOxHighlights(text).then(ranges => {
      if (current) setSelection({ text, ranges });
    }).catch(() => { if (current) setSelection({ text, ranges: [] }); });
    return () => { current = false; };
  }, [text]);
  return selection.text === text ? selection.ranges : [];
}
