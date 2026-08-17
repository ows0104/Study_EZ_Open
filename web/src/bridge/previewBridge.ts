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
  /**
   * `shared`일 때만 확장이 공개 `/share/` 링크를 만든다. 개인 예습에 공유가
   * 붙으면 남이 물은 것이 링크만으로 열리고, 관리자가 개인 예습을 하는 순간
   * 그 공유가 반 전체의 기본 링크를 덮는다.
   */
  mode: "shared" | "personal";
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
 * 기본 링크를 여는 참이라고 확장에 알린다.
 *
 * 공유 페이지에서 이어 물으면 ChatGPT가 그 시점까지를 복사해 **내 계정에 새
 * 대화를 만든다.** 원본은 안 바뀌므로 반의 기본 링크는 안전하지만, 그 사람에게는
 * 사실상 개인 예습이 하나 생긴 것이다. 확장이 연 탭이 아니라 지금까지는 놓쳤다.
 *
 * 확장이 없으면 아무 일도 안 일어난다 — 링크는 그냥 열린다.
 */
export function watchSharedLink(lectureId: string, shareUrl: string) {
  if (!extensionInstalled()) return;
  window.postMessage(
    { source: WEBAPP_SOURCE, type: MESSAGES.watchShare, lectureId, shareUrl },
    window.location.origin,
  );
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
