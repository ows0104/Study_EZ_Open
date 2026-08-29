// Study_EZ 페이지에 붙는다. 페이지는 확장을 직접 못 부르므로 여기가 통로다.

const { WEBAPP_SOURCE, EXTENSION_SOURCE, READY_ATTRIBUTE, VERSION, MESSAGES } = globalThis.STUDYEZ_PROTOCOL;

// 설치 여부는 이 표시로 본다. 없으면 웹앱이 설치 안내를 띄운다.
document.documentElement.setAttribute(READY_ATTRIBUTE, VERSION);

function reply(payload) {
  window.postMessage({ source: EXTENSION_SOURCE, ...payload }, window.location.origin);
}

window.addEventListener("message", (event) => {
  if (event.source !== window || event.origin !== window.location.origin) return;
  const message = event.data;
  if (!message || message.source !== WEBAPP_SOURCE) return;

  if (message.type === MESSAGES.openPreview) {
    const payload = message.payload;
    if (!payload || typeof payload.prompt !== "string" || !Array.isArray(payload.files)) return;
    chrome.runtime.sendMessage({ type: MESSAGES.openPreview, payload }, (response) => {
      const error = chrome.runtime.lastError?.message;
      reply({
        type: MESSAGES.openPreviewResult,
        requestId: payload.requestId,
        ok: Boolean(response?.ok) && !error,
        error: error || response?.error || "",
      });
    });
    return;
  }

  if (message.type === MESSAGES.linkSaved) {
    if (typeof message.lectureId !== "string" || typeof message.kind !== "string") return;
    chrome.runtime.sendMessage({ type: MESSAGES.linkSaved, lectureId: message.lectureId, kind: message.kind });
    return;
  }

  if (message.type === MESSAGES.watchShare) {
    if (
      typeof message.lectureId !== "string" ||
      typeof message.provider !== "string" ||
      typeof message.shareUrl !== "string"
    ) return;
    chrome.runtime.sendMessage({
      type: MESSAGES.watchShare,
      lectureId: message.lectureId,
      provider: message.provider,
      shareUrl: message.shareUrl,
    });
  }
});

// 대화가 끝나는 동안 이 탭이 잠들었을 수 있다. 그때 밀어 준 것을 놓쳤을 수
// 있으므로, 붙자마자 남아 있는 링크를 당겨 온다.
chrome.runtime.sendMessage({ type: MESSAGES.checkPending }, () => void chrome.runtime.lastError);

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type !== MESSAGES.linkReady) return false;
  reply({ type: MESSAGES.linkReady, lectureId: message.lectureId, kind: message.kind, url: message.url });
  return false;
});
