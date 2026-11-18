import { api } from "./api";

/** Report the observed site action; external AI completion is not observable here.
 *  share·mine = 예습 링크 열기 · create = 개인 예습 대화 만들기 · screate = 공통 예습 대화 만들기(관리자)
 *  rcreate = 개인 복습 대화 만들기 · rmine = 개인 복습 링크 열기 (server/app/models/previews.py) */
export function notePreviewAction(base: string, kind: "share" | "mine" | "create" | "screate" | "rcreate" | "rmine"): void {
  void api(`${base}/preview-open`, { method: "POST", body: JSON.stringify({ kind }) }).catch(() => {});
}
