import { useCallback, useEffect, useRef, useState } from "react";

/** Ordered writes run independently of reading/answering the next cached card. */
export function useStudyWrites() {
  const tail = useRef(Promise.resolve());
  const generation = useRef(0);
  const keys = useRef(new Set<string>());
  const count = useRef(0);
  const [saving, setSaving] = useState(false);
  const cancel = useCallback(() => { generation.current++; keys.current.clear(); }, []);
  const enqueue = useCallback((key: string, run: () => Promise<void>, failed: (cause: Error) => void) => {
    if (keys.current.has(key)) return false;
    keys.current.add(key);
    const version = generation.current;
    count.current++;
    setSaving(true);
    tail.current = tail.current.then(async () => {
      if (version !== generation.current) return;
      try { await run(); }
      catch (cause) {
        if (version !== generation.current) return;
        cancel();
        failed(cause as Error);
      }
    }).finally(() => {
      count.current--;
      setSaving(count.current > 0);
    });
    return true;
  }, [cancel]);
  useEffect(() => {
    const leaving = (event: BeforeUnloadEvent) => {
      if (!count.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", leaving);
    return () => window.removeEventListener("beforeunload", leaving);
  }, []);
  return { saving, enqueue, cancel, count };
}
