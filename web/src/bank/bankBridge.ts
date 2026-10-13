import { useEffect } from "react";
import { api } from "../api";
import { bumpPreviewVersion } from "../bridge/previewBridge";
import { EXTENSION_SOURCE, MESSAGES, WEBAPP_SOURCE } from "../bridge/protocol";

/**
 * 문제은행의 공유·개인 링크를 각각 저장한다. CLI 생성 일감은 별도 버튼으로 요청한다.
 * 저장에 성공한 링크만 확인을 돌려준다. 구버전에 남아 있는 본문 메시지도 링크만 회수한다.
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
      const links = legacy ? {
        ...(typeof data.url === "string" && data.url ? { conversationUrl: data.url } : {}),
        ...(typeof data.shareUrl === "string" && data.shareUrl ? { shareUrl: data.shareUrl } : {}),
      } : typeof data.url === "string" && data.url ? {
        [data.kind === "chatgpt_bank_share" ? "shareUrl" : "conversationUrl"]: data.url,
      } : {};
      if (!Object.keys(links).length) return;
      const path = `${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`;
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
