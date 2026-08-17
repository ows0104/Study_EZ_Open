import { useEffect } from "react";
import {
  EXTENSION_SOURCE,
  LINK_KINDS,
  MESSAGES,
  PREVIEW_TIMEOUT_MS,
  READY_ATTRIBUTE,
  WEBAPP_SOURCE,
  type LinkKind,
} from "./protocol";

export type PreviewFile = { id: string; filename: string; downloadUrl: string };

/** 확장이 설치돼 있는가. 없으면 안내를 띄우고 자동 열기를 하지 않는다. */
export function extensionInstalled() {
  return Boolean(document.documentElement.getAttribute(READY_ATTRIBUTE));
}

function sameWindow(event: MessageEvent) {
  return event.source === window && event.origin === window.location.origin;
}

/**
 * 서명 URL을 확장이 쓸 수 있는 꼴로 만든다.
 *
 * local-test에서는 서버가 `/api/local-storage/...`처럼 상대 경로를 내려준다.
 * 확장은 페이지 밖에서 fetch하므로 출처가 붙어 있어야 한다.
 */
export function absoluteUrl(url: string) {
  return new URL(url, window.location.origin).href;
}

/**
 * 확장에게 예습 대화를 열어 달라고 한다.
 *
 * 정해진 시간 안에 답이 없으면 오류다 — 설치는 됐지만 다시 로드해야 하는 상태를
 * 사용자가 알 수 있어야 한다.
 */
export function requestPreview(input: {
  requestId: string;
  lectureId: string;
  prompt: string;
  files: PreviewFile[];
}) {
  return new Promise<void>((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      window.removeEventListener("message", handle);
      reject(new Error("확장 프로그램이 응답하지 않습니다. chrome://extensions에서 다시 로드해 주세요."));
    }, PREVIEW_TIMEOUT_MS);

    function handle(event: MessageEvent) {
      if (!sameWindow(event)) return;
      const data = event.data;
      if (data?.source !== EXTENSION_SOURCE) return;
      if (data?.type !== MESSAGES.openPreviewResult || data?.requestId !== input.requestId) return;
      window.clearTimeout(timeout);
      window.removeEventListener("message", handle);
      if (data.ok) resolve();
      else reject(new Error(data.error || "확장 프로그램이 요청을 처리하지 못했습니다."));
    }

    window.addEventListener("message", handle);
    window.postMessage({ source: WEBAPP_SOURCE, type: MESSAGES.openPreview, payload: input }, window.location.origin);
  });
}

/**
 * 확장이 만들어 준 링크를 받아 저장한다.
 *
 * 저장이 끝나야 확장에게 확인을 돌려주고, 그때 확장이 대기 목록에서 지운다.
 * 저장에 실패하면(일반 사용자는 `PUT /preview`가 막혀 403) 확인을 안 보내므로
 * 링크는 확장에 남아 있다 — 관리자가 같은 대화를 열면 그때 저장된다.
 */
export function usePreviewLink(save: (input: { lectureId: string; kind: LinkKind; url: string }) => Promise<void>) {
  useEffect(() => {
    function handle(event: MessageEvent) {
      if (!sameWindow(event)) return;
      const data = event.data;
      if (data?.source !== EXTENSION_SOURCE || data?.type !== MESSAGES.linkReady) return;
      const lectureId = typeof data.lectureId === "string" ? data.lectureId : "";
      const url = typeof data.url === "string" ? data.url : "";
      const kind = typeof data.kind === "string" ? data.kind : "";
      if (!lectureId || !url || !LINK_KINDS.includes(kind as LinkKind)) return;

      void save({ lectureId, kind: kind as LinkKind, url }).then(() => {
        window.postMessage(
          { source: WEBAPP_SOURCE, type: MESSAGES.linkSaved, lectureId, kind },
          window.location.origin,
        );
      });
    }
    window.addEventListener("message", handle);
    return () => window.removeEventListener("message", handle);
  }, [save]);
}
