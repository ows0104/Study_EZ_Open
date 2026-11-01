import { api } from "./api";

/** Report the observed site action; external AI completion is not observable here. */
export function notePreviewAction(base: string, kind: "share" | "mine" | "create"): void {
  void api(`${base}/preview-open`, { method: "POST", body: JSON.stringify({ kind }) }).catch(() => {});
}
