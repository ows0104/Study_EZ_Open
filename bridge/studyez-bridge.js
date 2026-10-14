// Study_EZ 페이지에 붙는다. 페이지는 확장을 직접 못 부르므로 여기가 통로다.

const { WEBAPP_SOURCE, EXTENSION_SOURCE, READY_ATTRIBUTE, VERSION, MESSAGES } = globalThis.STUDYEZ_PROTOCOL;

// 설치 여부는 이 표시로 본다. 없으면 웹앱이 설치 안내를 띄운다.
let contextInvalidated = false;
const RELOAD_ERROR = "예습 브리지 연결이 끊겼습니다. chrome://extensions에서 확장을 다시 로드한 뒤 Study EZ와 AI 대화 탭을 새로고침해 주세요.";

function invalidateContext() {
  contextInvalidated = true;
  document.documentElement.removeAttribute(READY_ATTRIBUTE);
}

// 확장을 업데이트한 뒤에도 이전 페이지의 리스너는 남을 수 있다. 이때
// sendMessage는 콜백을 부르기 전에 예외를 던지므로 호출 자체도 감싼다.
function sendToExtension(message, done = () => {}) {
  let completed = false;
  function finish(response, error = "") {
    if (completed) return;
    completed = true;
    if (/extension context invalidated/i.test(error)) invalidateContext();
    done(response, contextInvalidated ? RELOAD_ERROR : error);
  }
  try {
    if (contextInvalidated || !chrome.runtime?.id) {
      invalidateContext();
      finish(undefined, RELOAD_ERROR);
      return;
    }
    chrome.runtime.sendMessage(message, (response) => {
      let error = "";
      try {
        error = chrome.runtime.lastError?.message || "";
      } catch (failure) {
        error = failure?.message || String(failure);
      }
      finish(response, error);
    });
  } catch (failure) {
    finish(undefined, failure?.message || String(failure));
  }
}

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
    sendToExtension({ type: MESSAGES.openPreview, payload }, (response, error) => {
      reply({
        type: MESSAGES.openPreviewResult,
        requestId: payload.requestId,
        ok: Boolean(response?.ok) && !error,
        error: error || response?.error || "",
      });
    });
    return;
  }

  if (message.type === MESSAGES.bankSaved) {
    if (typeof message.lectureId !== "string") return;
    sendToExtension({ type: MESSAGES.bankSaved, lectureId: message.lectureId });
    return;
  }

  if (message.type === MESSAGES.linkSaved) {
    if (typeof message.lectureId !== "string" || typeof message.kind !== "string") return;
    sendToExtension({ type: MESSAGES.linkSaved, lectureId: message.lectureId, kind: message.kind });
    return;
  }

  if (message.type === MESSAGES.watchShare) {
    if (
      typeof message.lectureId !== "string" ||
      typeof message.provider !== "string" ||
      typeof message.shareUrl !== "string"
    ) return;
    sendToExtension({
      type: MESSAGES.watchShare,
      lectureId: message.lectureId,
      provider: message.provider,
      shareUrl: message.shareUrl,
    });
  }
});

// 대화가 끝나는 동안 이 탭이 잠들었을 수 있다. 그때 밀어 준 것을 놓쳤을 수
// 있으므로, 붙자마자 남아 있는 링크를 당겨 온다.
function receiveMessage(message) {
  if (contextInvalidated) return false;
  if (message?.type === MESSAGES.bankReady) {
    reply({ type: MESSAGES.bankReady, lectureId: message.lectureId, raw: message.raw, url: message.url,
            promptVersion: message.promptVersion || "",
            ...(typeof message.shareUrl === "string" ? { shareUrl: message.shareUrl } : {}) });
    return false;
  }
  if (message?.type !== MESSAGES.linkReady) return false;
  reply({ type: MESSAGES.linkReady, lectureId: message.lectureId, kind: message.kind, url: message.url });
  return false;
}

try {
  if (!chrome.runtime?.id) {
    invalidateContext();
  } else {
    chrome.runtime.onMessage.addListener(receiveMessage);
    document.documentElement.setAttribute(READY_ATTRIBUTE, VERSION);
    sendToExtension({ type: MESSAGES.checkPending });
    // 저장 실패·다른 검수 작업과의 충돌 뒤에도 보관된 문항을 다시 전달한다.
    window.setInterval(() => {
      if (!contextInvalidated) sendToExtension({ type: MESSAGES.checkPending });
    }, 30_000);
  }
} catch {
  invalidateContext();
}
