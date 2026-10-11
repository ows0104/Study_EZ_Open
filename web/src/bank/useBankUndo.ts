import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { invalidateTimetable } from "../firstScreen";
import type { BankNext } from "../types/bank";

export function useBankUndo(base: string, token: string | null | undefined,
  onRestore: (next: BankNext) => void, onError: (error: string) => void, disabled = false) {
  const [undoBusy, setUndoBusy] = useState(false);
  const pending = useRef(false);
  const undo = useCallback(async () => {
    if (!token || disabled || pending.current) return;
    pending.current = true;
    setUndoBusy(true);
    onError("");
    try {
      const restored = await api<BankNext>(`${base}/undo`, {
        method: "POST", body: JSON.stringify({ reviewToken: token }),
      });
      invalidateTimetable();
      onRestore(restored);
    } catch (cause) { onError((cause as Error).message); }
    finally { pending.current = false; setUndoBusy(false); }
  }, [base, token, onRestore, onError, disabled]);
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (!token || disabled || event.defaultPrevented || event.repeat || event.isComposing
        || event.metaKey || event.altKey || event.shiftKey) return;
      if (document.querySelector("dialog[open], [role='dialog'][aria-modal='true']")) return;
      if (event.target instanceof HTMLElement && event.target.closest(
        "input, textarea, select, [contenteditable]:not([contenteditable='false']), [role='textbox']")) return;
      if (event.key.toLowerCase() !== "z" && event.code !== "KeyZ") return;
      event.preventDefault();
      void undo();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [token, disabled, undo]);
  return { undo, undoBusy, pending };
}
