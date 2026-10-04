import { useEffect } from "react";
import { api } from "../api";
import { bumpPreviewVersion } from "../bridge/previewBridge";
import { EXTENSION_SOURCE, MESSAGES, WEBAPP_SOURCE } from "../bridge/protocol";
import { BANK_PROMPT_VERSION } from "./prompt";

/**
 * 확장이 ChatGPT 탭에서 받아 온 Quiz Bank 답 본문을 서버에 저장한다.
 *
 * 예습 링크(`usePreviewLink`)와 같은 규칙이다 — **저장이 끝나야 확장에 확인을 돌려주고**, 그때
 * 확장이 대기 목록에서 지운다. 저장이 실패하면(관리자가 아니면 403) 확인을 안 보내므로 본문은
 * 확장에 남는다. 저장되면 서버가 러너의 일감을 세운다.
 */
export function useBankLink() {
  useEffect(() => {
    function handle(event: MessageEvent) {
      if (event.source !== window || event.origin !== window.location.origin) return;
      const data = event.data;
      if (data?.source !== EXTENSION_SOURCE || data?.type !== MESSAGES.bankReady) return;
      const lectureId = typeof data.lectureId === "string" ? data.lectureId : "";
      const raw = typeof data.raw === "string" ? data.raw : "";
      const [subject, runId] = lectureId.split("/");
      if (!subject || !runId || !raw) return;
      const path = `${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`;
      void api(`/api/admin/lectures/${path}/bank-response`, {
        method: "PUT",
        body: JSON.stringify({
          raw,
          conversationUrl: typeof data.url === "string" ? data.url : "",
          promptVersion: BANK_PROMPT_VERSION,
        }),
      })
        .then(() => {
          window.postMessage({ source: WEBAPP_SOURCE, type: MESSAGES.bankSaved, lectureId }, window.location.origin);
          bumpPreviewVersion();
        })
        .catch(() => undefined);
    }
    window.addEventListener("message", handle);
    return () => window.removeEventListener("message", handle);
  }, []);
}
