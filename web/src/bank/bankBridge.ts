import { useEffect } from "react";
import { api } from "../api";
import { bumpPreviewVersion } from "../bridge/previewBridge";
import { EXTENSION_SOURCE, MESSAGES, WEBAPP_SOURCE } from "../bridge/protocol";

/**
 * 완성된 웹 문항을 저장해 CLI 검수·게시를 시작한다. 링크는 별도로 저장한다.
 * 서버 저장에 성공한 뒤에만 확인을 돌려줘 실패한 본문은 확장에 남는다.
 */
export function useBankLink() {
  useEffect(() => {
    function handle(event: MessageEvent) {
      if (event.source !== window || event.origin !== window.location.origin) return;
      const data = event.data;
      if (data?.source !== EXTENSION_SOURCE) return;
      const legacy = data?.type === MESSAGES.bankReady;
      const bankLink = data?.type === MESSAGES.linkReady
        && ["chatgpt_bank", "chatgpt_bank_share"].includes(data.kind);
      if (!legacy && !bankLink) return;
      const lectureId = typeof data.lectureId === "string" ? data.lectureId : "";
      const [subject, runId] = lectureId.split("/");
      if (!subject || !runId || lectureId.split("/").length !== 2) return;
      const path = `${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`;
      if (legacy && typeof data.raw === "string" && data.raw.length >= 200
          && data.raw.length <= 2_000_000 && data.raw.trimEnd().endsWith("STUDYEZ_BANK_COMPLETE")) {
        void api(`/api/admin/lectures/${path}/bank-response`, {
          method: "PUT", body: JSON.stringify({ raw: data.raw, conversationUrl: data.url || "",
            ...(data.shareUrl ? { shareUrl: data.shareUrl } : {}) }),
        }).then(() => {
          window.postMessage({ source: WEBAPP_SOURCE, type: MESSAGES.bankSaved, lectureId }, window.location.origin);
          bumpPreviewVersion();
        }).catch(() => undefined);
        return;
      }
      const links = legacy ? {
        ...(typeof data.url === "string" && data.url ? { conversationUrl: data.url } : {}),
        ...(typeof data.shareUrl === "string" && data.shareUrl ? { shareUrl: data.shareUrl } : {}),
      } : typeof data.url === "string" && data.url ? {
        [data.kind === "chatgpt_bank_share" ? "shareUrl" : "conversationUrl"]: data.url,
      } : {};
      if (!Object.keys(links).length) return;
      void api(`/api/admin/lectures/${path}/bank/links`, {
        method: "PUT",
        body: JSON.stringify(links),
      })
        .then(() => {
          window.postMessage({ source: WEBAPP_SOURCE, type: legacy ? MESSAGES.bankSaved : MESSAGES.linkSaved,
            lectureId, ...(legacy ? {} : { kind: data.kind }) }, window.location.origin);
          bumpPreviewVersion();
        })
        .catch(() => undefined);
    }
    window.addEventListener("message", handle);
    return () => window.removeEventListener("message", handle);
  }, []);
}
