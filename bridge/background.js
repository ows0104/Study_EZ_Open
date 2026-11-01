importScripts("protocol.js", "bank-file.js", "bank-download.js");

const { WEBAPP_SOURCE, MESSAGES, LINK_KINDS } = globalThis.STUDYEZ_PROTOCOL;

const TAB_PAYLOAD = "studyez-tab:";
const PENDING_LINK = "studyez-pending:";
/** Quiz Bank 답 본문. 웹앱이 저장했다고 회신할 때까지 둔다(링크와 같은 규칙). */
const PENDING_BANK = "studyez-bank:";
const BANK_MARK = "STUDYEZ_BANK_COMPLETE";
const BANK_MAX_CHARS = 2_000_000;
/**
 * AI 서비스 탭 → `{ lectureId, provider, mode, webappTabId }`.
 *
 * 이 기록이 있는 탭에서 나온 링크만 강의에 붙는다. 강의 id는 페이지가 보내는
 * 메시지가 아니라 여기서 읽는다 — 페이지가 아무 강의에나 링크를 달 수 없다.
 */
const TAB_WATCH = "studyez-watch:";
/** 기본 링크의 share id → 어느 강의였나. 갈라져 나온 대화를 그 강의로 돌리는 데 쓴다. */
const SHARE_ORIGIN = "studyez-share-origin:";

const AI_PROVIDERS = {
  chatgpt: { origin: "https://chatgpt.com", startUrl: "https://chatgpt.com/" },
  gemini: { origin: "https://gemini.google.com", startUrl: "https://gemini.google.com/app" },
  claude: { origin: "https://claude.ai", startUrl: "https://claude.ai/new" },
};
const R2_ORIGIN = "https://d0ec59549fea0c13f1b7fe9f724df93b.r2.cloudflarestorage.com";

/**
 * 여기서 온 요청만 받는다. 확장은 웹앱이 시키는 대로 남의 사이트에 파일을
 * 넣으므로, 시킬 수 있는 쪽을 좁히는 것이 첫 관문이다.
 *
 * manifest의 `content_scripts[0].matches`와 **같이** 고친다. 한쪽만 고치면
 * 스크립트는 붙는데 배경이 안 받거나, 그 반대가 된다.
 */
const WEBAPP_ORIGINS = new Set(["https://studyez.kr", "http://localhost:5173"]);

function originOf(sender) {
  try {
    return new URL(sender.tab?.url || sender.url || "").origin;
  } catch {
    return "";
  }
}

const fromWebapp = (sender) => WEBAPP_ORIGINS.has(originOf(sender));
function providerForUrl(value) {
  try {
    const origin = new URL(value).origin;
    return Object.keys(AI_PROVIDERS).find((provider) => AI_PROVIDERS[provider].origin === origin) || "";
  } catch {
    return "";
  }
}

const providerForSender = (sender) => providerForUrl(sender.tab?.url || sender.url || "");

/**
 * 자료를 어디서 받아도 되는가.
 *
 * 확장은 웹앱이 시키는 주소로 fetch를 하므로, 여기가 유일한 관문이다. 배포는
 * 서명된 R2 주소이고 로컬 테스트는 Study_EZ 서버의 산출물 경로만 받는다.
 */
function allowedDownload(value) {
  try {
    const url = new URL(value);
    if (url.origin === R2_ORIGIN) return true;
    const localOrigins = ["http://localhost:5173", "http://localhost:8000", "http://127.0.0.1:8000"];
    return localOrigins.includes(url.origin) && url.pathname.startsWith("/api/local-storage/lectures/");
  } catch {
    return false;
  }
}

/** 제공자 계정에 귀속되는 개인 대화 주소인가. */
function isConversationUrl(provider, value) {
  try {
    const url = new URL(value);
    if (url.origin !== AI_PROVIDERS[provider]?.origin) return false;
    if (provider === "chatgpt") return /^\/(?:g\/[^/]+\/)?c\/[A-Za-z0-9_:-]+/.test(url.pathname);
    if (provider === "gemini") return /^\/app\/[A-Za-z0-9_-]+/.test(url.pathname);
    if (provider === "claude") return /^\/chat\/[A-Za-z0-9-]+/.test(url.pathname);
    return false;
  } catch {
    return false;
  }
}

/** 공개 공유 주소의 제공자와 id. 같은 링크를 어디서 열든 이 값으로 알아본다. */
function shareIdentity(provider, value) {
  try {
    const url = new URL(value);
    if (provider === "chatgpt" && url.origin === AI_PROVIDERS.chatgpt.origin) {
      const match = /^\/share\/(?:e\/)?([A-Za-z0-9_-]+)/.exec(url.pathname);
      return match ? { provider, id: match[1] } : null;
    }
    if (provider === "claude" && url.origin === AI_PROVIDERS.claude.origin) {
      const match = /^\/share\/([A-Za-z0-9-]+)/.exec(url.pathname);
      return match ? { provider, id: match[1] } : null;
    }
    if (provider === "gemini") {
      const direct = url.origin === AI_PROVIDERS.gemini.origin && /^\/share\/([A-Za-z0-9_-]+)/.exec(url.pathname);
      const short = url.origin === "https://g.co" && /^\/gemini\/share\/([A-Za-z0-9_-]+)/.exec(url.pathname);
      const match = direct || short;
      return match ? { provider, id: match[1] } : null;
    }
    return null;
  } catch {
    return null;
  }
}

function shareIdentityForUrl(value) {
  return Object.keys(AI_PROVIDERS).map((provider) => shareIdentity(provider, value)).find(Boolean) || null;
}

function bytesToBase64(bytes) {
  let binary = "";
  const step = 0x8000;
  for (let index = 0; index < bytes.length; index += step) {
    binary += String.fromCharCode(...bytes.subarray(index, index + step));
  }
  return btoa(binary);
}

const pendingKey = (webappTabId, lectureId, kind) => `${PENDING_LINK}${webappTabId}:${lectureId}:${kind}`;
const bankKey = (webappTabId, lectureId) => `${PENDING_BANK}${webappTabId}:${lectureId}`;

/**
 * 이 탭으로 갈 링크를 전부 밀어 준다.
 *
 * 웹앱이 "저장했다"고 회신하기 전에는 지우지 않는다. 탭이 닫혔거나 잠들어
 * 전달이 실패해도 링크를 잃지 않고 다음 기회에 다시 보낸다는 뜻이다.
 */
async function deliverPending(webappTabId) {
  const stored = await chrome.storage.session.get(null);
  const prefix = `${PENDING_LINK}${webappTabId}:`;
  const bankPrefix = `${PENDING_BANK}${webappTabId}:`;
  for (const [key, entry] of Object.entries(stored)) {
    if (key.startsWith(bankPrefix)) {
      try {
        await chrome.tabs.sendMessage(webappTabId, {
          type: MESSAGES.bankReady, lectureId: entry.lectureId, raw: entry.raw, url: entry.url,
          promptVersion: entry.promptVersion || "",
          ...(entry.responseFile ? { responseFile: entry.responseFile } : {}),
          ...(entry.responseFile && entry.manualFile ? { manualFile: true } : {}),
          ...(typeof entry.shareUrl === "string" ? { shareUrl: entry.shareUrl } : {}),
        });
      } catch {
        // 지금은 닿지 않는다. 남겨 두고 다음 기회에 다시 보낸다.
      }
      continue;
    }
    if (!key.startsWith(prefix)) continue;
    try {
      await chrome.tabs.sendMessage(webappTabId, {
        type: MESSAGES.linkReady,
        lectureId: entry.lectureId,
        kind: entry.kind,
        url: entry.url,
      });
    } catch {
      // 지금은 닿지 않는다. 남겨 두고 다음 기회에 다시 보낸다.
    }
  }
}

/**
 * 이 탭에서 나오는 예습 링크를 받겠다고 적어 둔다.
 *
 * 콘텐츠 스크립트에 알려도 주고, 실패해도 그만이다 — 아직 안 붙었으면 스스로
 * 세션 저장소에서 집어 간다.
 */
async function watchTab(tabId, watch) {
  await chrome.storage.session.set({ [`${TAB_WATCH}${tabId}`]: watch });
  // 기다리지 않는다. 갓 연 탭에는 아직 콘텐츠 스크립트가 없어 반드시 실패하는데,
  // 그 실패를 기다리면 웹앱의 "열기" 응답이 그만큼 늦는다.
  void chrome.tabs
    .sendMessage(tabId, {
      type: "STUDYEZ_WATCH_READY",
      promptVersion: watch.promptVersion || "",
      lectureId: watch.lectureId,
      provider: watch.provider,
      mode: watch.mode,
    })
    .catch(() => undefined);
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  // 기본 링크를 연 탭인가. 맞으면 그 탭도 감시 대상으로 올린다 — 여기서 이어
  // 물으면 AI 서비스가 그 시점까지를 복사해 새 개인 대화를 만든다.
  //
  // `mode`는 personal이다. 갈라져 나온 것은 그 사람 것이지 반의 것이 아니므로
  // 공유를 다시 발행하면 안 된다.
  const shared = changeInfo.url ? shareIdentityForUrl(changeInfo.url) : null;
  if (shared) {
    const originKey = `${SHARE_ORIGIN}${shared.provider}:${shared.id}`;
    void chrome.storage.session
      .get(originKey)
      .then((stored) => {
        const origin = stored[originKey];
        if (!origin) return;
        return watchTab(tabId, {
          lectureId: origin.lectureId,
          provider: shared.provider,
          mode: "personal",
          webappTabId: origin.webappTabId,
        });
      })
      .catch(() => undefined);
  }

  if (changeInfo.status === "complete") void deliverPending(tabId).catch(() => undefined);
});

chrome.tabs.onActivated.addListener(({ tabId }) => void deliverPending(tabId).catch(() => undefined));

chrome.tabs.onRemoved.addListener((tabId) => {
  void chrome.storage.session
    .get(null)
    .then((stored) => {
      const stale = Object.keys(stored).filter(
        (key) => key.startsWith(`${PENDING_LINK}${tabId}:`) || key.startsWith(`${PENDING_BANK}${tabId}:`),
      );
      return chrome.storage.session.remove([`${TAB_PAYLOAD}${tabId}`, `${TAB_WATCH}${tabId}`, ...stale]);
    })
    .catch(() => undefined);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === MESSAGES.checkPending) {
    if (!fromWebapp(sender) || !sender.tab?.id) return false;
    void deliverPending(sender.tab.id).catch(() => undefined);
    return false;
  }

  if (message?.type === MESSAGES.watchShare) {
    if (!fromWebapp(sender) || !sender.tab?.id) return false;
    const shared = shareIdentity(message.provider, message.shareUrl || "");
    if (!shared || typeof message.lectureId !== "string" || !message.lectureId) return false;
    void chrome.storage.session.set({
      [`${SHARE_ORIGIN}${shared.provider}:${shared.id}`]: {
        lectureId: message.lectureId,
        webappTabId: sender.tab.id,
      },
    });
    return false;
  }

  if (message?.type === MESSAGES.bankSaved) {
    if (!fromWebapp(sender) || !sender.tab?.id || !message.lectureId) return false;
    const key = bankKey(sender.tab.id, message.lectureId);
    void chrome.storage.session.get(key).then(async stored => {
      const pending = stored[key];
      if (pending?.sourceTabId && pending.responseFile?.sha256) {
        await chrome.tabs.sendMessage(pending.sourceTabId, {type:'STUDYEZ_BANK_FILE_SAVED',
          sha256:pending.responseFile.sha256, filename:pending.responseFile.filename}).catch(() => {});
      }
      await chrome.storage.session.remove(key);
    }).catch(() => {});
    return false;
  }

  if (message?.type === 'STUDYEZ_BANK_DOWNLOAD_FILE') {
    if (providerForSender(sender) !== 'chatgpt' || !sender.tab?.id) return false;
    void chrome.storage.session.get(`${TAB_WATCH}${sender.tab.id}`).then(async stored => {
      const watch = stored[`${TAB_WATCH}${sender.tab.id}`];
      const target = globalThis.StudyEZBankFile.lectureTarget(watch?.lectureId, watch?.promptVersion);
      const conversation = /^\/(?:g\/[^/]+\/)?c\/([A-Za-z0-9_:-]+)/.exec(new URL(sender.tab.url).pathname)?.[1];
      if (watch?.mode !== 'bank' || !globalThis.StudyEZBankFile.required(target) || !conversation) {
        sendResponse({ok:false}); return;
      }
      target.filename = `study-ez-${target.runId}-bank.md`;
      const results = await chrome.scripting.executeScript({target:{tabId:sender.tab.id},world:'MAIN',
        func:captureBankDownload,args:[target,conversation]});
      const file = results.find(item => item.frameId === 0)?.result;
      if (!file?.raw) { sendResponse({ok:false,error:file?.error || 'MD 파일 다운로드를 기다립니다.'}); return; }
      globalThis.StudyEZBankFile.inspect(file.raw,target,file.filename);
      sendResponse({ok:true,raw:file.raw,filename:file.filename});
    }).catch(error => sendResponse({ok:false,error:error.message}));
    return true;
  }

  // Quiz Bank 탭이 끝난 답의 본문을 보낸다. **강의 id 는 감시 기록에서 읽는다** — 링크와 같다.
  // bank 로 연 ChatGPT 탭에서 온 것만, 완료 표시가 있는 것만 받는다.
  if (message?.type === "STUDYEZ_BANK_ANSWER") {
    if (providerForSender(sender) !== "chatgpt" || !sender.tab?.id) return false;
    const raw = typeof message.raw === "string" ? message.raw : "";
    if (!raw.includes(BANK_MARK) || raw.length > BANK_MAX_CHARS) return false;
    const key = `${TAB_WATCH}${sender.tab.id}`;
    void chrome.storage.session
      .get(key)
      .then(async (stored) => {
        const watch = stored[key];
        if (!watch || watch.mode !== "bank") { sendResponse({ ok: false }); return; }
        const target = globalThis.StudyEZBankFile?.lectureTarget(watch.lectureId, watch.promptVersion);
        if (globalThis.StudyEZBankFile?.required(target) && !message.responseFile) {
          sendResponse({ ok: false, error: "실제 .md 파일 원문이 필요합니다." }); return;
        }
        if (message.responseFile) {
          try { globalThis.StudyEZBankFile.inspect(raw, target, message.responseFile.filename); }
          catch (error) { sendResponse({ ok: false, error: error.message }); return; }
        }
        const url = isConversationUrl("chatgpt", message.url || "") ? message.url : "";
        const shareUrl = shareIdentity("chatgpt", message.shareUrl || "") ? message.shareUrl : undefined;
        await chrome.storage.session.set({
          [bankKey(watch.webappTabId, watch.lectureId)]: { lectureId: watch.lectureId, raw, url,
            sourceTabId: sender.tab.id,
            promptVersion: watch.promptVersion || "",
            ...(message.responseFile ? { responseFile: message.responseFile } : {}),
            ...(message.responseFile && message.manualFile === true ? { manualFile: true } : {}),
            ...(shareUrl ? { shareUrl } : {}) },
        });
        sendResponse({ ok: true });
        await deliverPending(watch.webappTabId);
      })
      .catch(() => sendResponse({ ok: false }));
    return true;
  }

  if (message?.type === MESSAGES.linkSaved) {
    if (!fromWebapp(sender) || !sender.tab?.id || !message.lectureId || !message.kind) return false;
    void chrome.storage.session.remove(pendingKey(sender.tab.id, message.lectureId, message.kind));
    return false;
  }

  // 이 탭이 어느 강의의 무슨 몫인지 콘텐츠 스크립트가 물어본다.
  if (message?.type === "STUDYEZ_GET_WATCH") {
    if (!providerForSender(sender) || !sender.tab?.id) {
      sendResponse({ ok: false });
      return false;
    }
    const key = `${TAB_WATCH}${sender.tab.id}`;
    void chrome.storage.session
      .get(key)
      .then((stored) =>
        sendResponse(stored[key] ? {
          ok: true,
          lectureId: stored[key].lectureId,
          provider: stored[key].provider,
          mode: stored[key].mode,
          promptVersion: stored[key].promptVersion || "",
        } : { ok: false }),
      )
      .catch(() => sendResponse({ ok: false }));
    return true;
  }

  if (message?.type === "STUDYEZ_SHARE_LINK" || message?.type === "STUDYEZ_CONVERSATION_LINK") {
    const provider = providerForSender(sender);
    if (!provider || !sender.tab?.id) return false;
    const share = message.type === "STUDYEZ_SHARE_LINK";
    const url = typeof message.url === "string" ? message.url : "";
    if (share ? !shareIdentity(provider, url) : !isConversationUrl(provider, url)) return false;
    const key = `${TAB_WATCH}${sender.tab.id}`;
    // 강의 id는 메시지가 아니라 감시 기록에서 가져온다. 페이지가 아무 강의에나
    // 링크를 붙일 수 없다는 뜻이다.
    void chrome.storage.session
      .get(key)
      .then(async (stored) => {
        const watch = stored[key];
        if (!watch || watch.provider !== provider) return;
        // Quiz Bank 로 연 대화는 예습 링크가 아니다. 저장하면 관리자의 개인 예습 자리를 덮는다.
        // 공유는 기본 링크를 만들 때만 낸다.
        //
        // 개인 예습까지 공개 `/share/`를 발행하면 두 가지가 잘못된다 — 남이
        // 물은 것이 링크만 있으면 열리게 되고, 관리자가 개인 예습을 하는 순간
        // 그 공유가 반 전체의 기본 링크를 덮는다.
        if (share && !["shared", "bank"].includes(watch.mode)) return;
        const kind = watch.mode === "bank" ? (share ? "chatgpt_bank_share" : "chatgpt_bank")
          : share ? `${provider}_share` : watch.mode === "review" ? `${provider}_review` : provider;
        await chrome.storage.session.set({
          [pendingKey(watch.webappTabId, watch.lectureId, kind)]: { lectureId: watch.lectureId, kind, url },
        });
        await deliverPending(watch.webappTabId);
      })
      .catch(() => undefined);
    return false;
  }

  // AI 서비스 탭이 자기 몫의 자료를 가져간다. 한 번 주고 지운다.
  if (message?.type === "STUDYEZ_GET_PAYLOAD") {
    if (!providerForSender(sender) || !sender.tab?.id) {
      sendResponse({ ok: false, error: "AI 탭을 확인하지 못했습니다." });
      return false;
    }
    const key = `${TAB_PAYLOAD}${sender.tab.id}`;
    void chrome.storage.session
      .get(key)
      .then((stored) => {
        const payload = stored[key] || null;
        if (payload) void chrome.storage.session.remove(key);
        sendResponse({ ok: true, payload });
      })
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message?.type === "STUDYEZ_PREPARE_GEMINI_FILE_INPUT") {
    if (providerForSender(sender) !== "gemini" || !sender.tab?.id) {
      sendResponse({ ok: false, error: "Gemini 탭을 확인하지 못했습니다." });
      return false;
    }
    void chrome.scripting.executeScript({
      target: { tabId: sender.tab.id },
      world: "MAIN",
      func: () => {
        if (window.__studyezGeminiFileCaptureActive) return;
        window.__studyezGeminiFileCaptureActive = true;
        const originalClick = HTMLInputElement.prototype.click;
        const restore = () => {
          if (HTMLInputElement.prototype.click === patchedClick) HTMLInputElement.prototype.click = originalClick;
          window.__studyezGeminiFileCaptureActive = false;
        };
        function patchedClick(...args) {
          if (this.type === "file") {
            this.setAttribute("data-studyez-gemini-file-input", "ready");
            this.style.display = "none";
            if (!this.isConnected) document.documentElement.appendChild(this);
            restore();
            return;
          }
          return originalClick.apply(this, args);
        }
        HTMLInputElement.prototype.click = patchedClick;
        window.setTimeout(restore, 10_000);
      },
    }).then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message?.type === "STUDYEZ_VERIFY_SHARE_LINK") {
    const provider = providerForSender(sender);
    const shared = shareIdentity(provider, message.url || "");
    if (!provider || !shared) {
      sendResponse({ ok: false });
      return false;
    }
    void fetch(message.url, { credentials: "omit", redirect: "follow" })
      .then((response) => {
        const finalUrl = response.url || message.url;
        const finalIdentity = shareIdentity(provider, finalUrl) || shared;
        sendResponse({
          ok: response.ok && Boolean(finalIdentity),
          url: finalIdentity && shareIdentity(provider, finalUrl) ? finalUrl : message.url,
        });
      })
      .catch(() => sendResponse({ ok: false }));
    return true;
  }

  if (message?.type !== MESSAGES.openPreview || !fromWebapp(sender)) return false;

  const payload = message.payload;
  const providerConfig = AI_PROVIDERS[payload?.provider];
  if (!payload?.requestId || !payload.lectureId || !providerConfig || typeof payload.prompt !== "string" || !Array.isArray(payload.files)) {
    sendResponse({ ok: false, error: "전달된 예습 자료 형식이 올바르지 않습니다." });
    return false;
  }
  // 안 주면 개인으로 본다. 공유는 명시적으로 시킬 때만 만든다.
  // `bank` 는 Quiz Bank — 답 본문을 읽는 것이 ChatGPT 쪽(`chatgpt-share.js`)에만 있다.
  const mode = ["shared", "bank", "review"].includes(payload.mode) ? payload.mode : "personal";
  if (mode === "bank" && payload.provider !== "chatgpt") {
    sendResponse({ ok: false, error: "Quiz Bank는 ChatGPT로만 만듭니다." });
    return false;
  }
  if (!payload.files.length || !payload.files.every((file) => file?.filename && allowedDownload(file.downloadUrl))) {
    sendResponse({ ok: false, error: "허용되지 않은 자료 주소가 포함되어 있습니다." });
    return false;
  }

  void chrome.tabs
    .create({ url: providerConfig.startUrl })
    .then(async (tab) => {
      if (!tab.id) throw new Error("새 AI 서비스 탭을 열지 못했습니다.");
      if (!sender.tab?.id) throw new Error("Study_EZ 탭을 확인하지 못했습니다.");
      await chrome.storage.session.set({ [`${TAB_PAYLOAD}${tab.id}`]: payload });
      await watchTab(tab.id, {
        lectureId: payload.lectureId,
        promptVersion: typeof payload.promptVersion === "string" ? payload.promptVersion : "",
        provider: payload.provider,
        mode,
        webappTabId: sender.tab.id,
      });
    })
    .then(() => sendResponse({ ok: true }))
    .catch((error) => sendResponse({ ok: false, error: String(error) }));
  return true;
});

/**
 * 자료 전달.
 *
 * 콘텐츠 스크립트는 R2에 직접 못 간다(교차 출처). 배경이 받아서 조각내 넘긴다.
 */
chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== "studyez-file-stream") return;
  port.onMessage.addListener(async (message) => {
    if (message?.type !== "DOWNLOAD_FILE" || !allowedDownload(message.downloadUrl)) {
      port.postMessage({ type: "FILE_ERROR", fileId: message?.fileId || "", error: "허용되지 않은 다운로드 주소입니다." });
      return;
    }
    try {
      const response = await fetch(message.downloadUrl);
      if (!response.ok || !response.body) throw new Error(`자료를 받지 못했습니다 (HTTP ${response.status})`);
      port.postMessage({ type: "FILE_START", fileId: message.fileId, filename: message.filename });
      const reader = response.body.getReader();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        port.postMessage({ type: "FILE_CHUNK", fileId: message.fileId, chunk: bytesToBase64(value) });
      }
      port.postMessage({ type: "FILE_END", fileId: message.fileId });
    } catch (error) {
      port.postMessage({ type: "FILE_ERROR", fileId: message.fileId, error: String(error) });
    }
  });
});

void LINK_KINDS;
void WEBAPP_SOURCE;
