import { useEffect, useState } from "react";
import type { PreviewProvider } from "../types/lectures";
import {
  EXTENSION_SOURCE,
  LINK_KINDS,
  MESSAGES,
  PREVIEW_TIMEOUT_MS,
  READY_ATTRIBUTE,
  WEBAPP_SOURCE,
  type LinkKind,
} from "./protocol";

/** 족보 조각 .md를 PDF로 처리하지 않도록 원본 contentType을 함께 전달한다. */
export type PreviewFile = { id: string; filename: string; downloadUrl: string; contentType?: string };

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
  provider: PreviewProvider;
  /**
   * `shared`일 때만 확장이 공개 `/share/` 링크를 만든다. 개인 예습에 공유가
   * 붙으면 남이 물은 것이 링크만으로 열리고, 관리자가 개인 예습을 하는 순간
   * 그 공유가 반 전체의 기본 링크를 덮는다.
   *
   * `bank` 는 Quiz Bank(관리자)다. 링크 대신 끝난 답의 본문이 돌아온다(`bank/bankBridge.ts`).
   */
  mode: "shared" | "personal" | "review" | "bank";
  prompt: string;
  files: PreviewFile[];
  /** 기본 링크의 자동전송만 true. 개인 링크와 문제 생성은 확인 후 직접 전송한다. */
  autoSend: boolean;
}) {
  const version = document.documentElement.getAttribute(READY_ATTRIBUTE) || "";
  const parts = version.split(".").map(Number);
  if (input.mode === "review" && !(parts[0] > 1 || (parts[0] === 1 && (parts[1] > 3 || (parts[1] === 3 && parts[2] >= 5))))) {
    return Promise.reject(new Error("복습 개인 링크를 만들려면 브리지 1.3.5 이상으로 업데이트하고 확장과 이 페이지를 새로고침해 주세요."));
  }
  if (!(parts[0] > 1 || (parts[0] === 1 && (parts[1] > 3 || (parts[1] === 3 && parts[2] >= 3))))) {
    return Promise.reject(new Error("자료를 넣으려면 예습 브리지 1.3.3 이상으로 업데이트하고 확장과 이 페이지를 새로고침해 주세요."));
  }
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
 * 공유 페이지에서 이어 물으면 AI 서비스가 그 시점까지를 복사해 **내 계정에 새
 * 대화를 만든다.** 원본은 안 바뀌므로 반의 기본 링크는 안전하지만, 그 사람에게는
 * 사실상 개인 예습이 하나 생긴 것이다. 확장이 연 탭이 아니라 지금까지는 놓쳤다.
 *
 * 확장이 없으면 아무 일도 안 일어난다 — 링크는 그냥 열린다.
 */
export function watchSharedLink(lectureId: string, provider: PreviewProvider, shareUrl: string) {
  if (!extensionInstalled()) return;
  window.postMessage(
    { source: WEBAPP_SOURCE, type: MESSAGES.watchShare, lectureId, provider, shareUrl },
    window.location.origin,
  );
}

/**
 * 예습 링크가 저장됐다는 신호.
 *
 * 링크는 **화면 밖에서** 온다 — 다른 탭에서 대화가 끝나면 확장이 밀어 준다.
 * 그때 열려 있는 패널은 자기가 부른 강의 상세를 그대로 들고 있어서, 저장은
 * 됐는데 버튼은 계속 "개인 예습 시작"으로 남아 있었다. 칸을 다시 눌러도
 * 같은 강의면 패널이 다시 붙지 않아 새로고침 전까지 안 바뀌었다.
 */
let previewVersion = 0;
const versionListeners = new Set<(value: number) => void>();

export function bumpPreviewVersion() {
  previewVersion += 1;
  versionListeners.forEach((notify) => notify(previewVersion));
}

export function usePreviewVersion() {
  const [value, setValue] = useState(previewVersion);
  useEffect(() => {
    versionListeners.add(setValue);
    return () => void versionListeners.delete(setValue);
  }, []);
  return value;
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

/**
 * 이 기기에 확장을 설치할 수 있는가.
 *
 * **모바일 브라우저에는 크롬 확장이 없다.** 그래서 「설치하세요」 카드는 모바일에서
 * 갈 데가 없는 곳을 가리킨다 — 스토어를 열어도 설치 단추가 없다.
 *
 * 다만 **링크 자체는 그냥 주소라 확장 없이도 열린다.** 컴퓨터에서 만들어 둔 개인
 * 링크를 폰에서 여는 것은 원래 되던 일이고, 설치 안내가 그 자리를 덮고 있었을
 * 뿐이다(2026-09-18 관리자 지시).
 *
 * UA 로 재는 것은 확실하지 않다 — 틀려도 **카드 하나가 남거나 없어질 뿐**이고
 * 링크는 어느 쪽이든 그대로 선다. 그 선에서만 쓴다.
 */
export function extensionPossible() {
  const mobile = (navigator as Navigator & { userAgentData?: { mobile?: boolean } }).userAgentData?.mobile;
  if (typeof mobile === "boolean") return !mobile;
  if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) return false;
  // iPadOS 는 데스크톱 UA 를 보낸다. 터치 점이 여럿인 Mac 은 사실상 그것이다.
  return !(/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
}
